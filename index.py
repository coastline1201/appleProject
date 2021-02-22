from datetime import datetime
from flask import Flask
from flask import flash, redirect, render_template, request, send_from_directory, url_for
import copy
import csv
import os
import time

ALLOWED_EXTENSIONS = {'csv'}
FILE_HEADERS = {
	'order_file':['customer', 'product', 'date', 'quantity'],
	'supply_file':['site', 'product', 'date', 'quantity'],
	'sourcing_file':['site', 'customer', 'product'],
}

app = Flask(__name__)
app.config['SECRET_KEY'] = '123456'

@app.route('/', methods=['GET', 'POST'])
def index():
	has_file = {}
	for file_name in FILE_HEADERS.keys():
		has_file[file_name] = os.path.isfile('uploads/' + file_name + '.csv')

	if request.method == 'POST':
		# check if the post request has the file part
		has_error = False
		for file_name in FILE_HEADERS.keys():
			has_error = check_file(file_name, request.files, has_file) or has_error
		if has_error:
			return redirect(url_for('index'))
		return redirect(url_for('plan'))

	
	return render_template('index.html', has_file = has_file)

def check_file(file_name, files, has_file):
	print(file_name)
	print(has_file[file_name])
	if file_name not in request.files or files[file_name].filename == '' or files[file_name] is None:
		if not has_file[file_name]:
			flash(file_name + ' is not uploaded')
			return True
		else:
			return False
	file = files[file_name]
	if not allowed_file(file.filename):
		flash('The format for file ' + file.filename + ' is not supported')
		return True
	file.save('uploads/' + file_name + '.csv')
	return False

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/plan')
def plan():
	orders = readOrderFile()
	sourcing_map = readSourcingFile()
	supply_map = readSupplyFile()
	if orders is None or sourcing_map is None or supply_map is None:
		return redirect(url_for('index'))

	plan = allocate(orders, sourcing_map, supply_map)
	writePlanFile(plan)
	return render_template('plan.html', plan = plan)

@app.route('/download/<path:filename>', methods=['GET'])
def download(filename):
	return send_from_directory('uploads/', filename + '.csv', as_attachment=True)

def allocate(orders, sourcing_map, supply_map):
	results = {}
	unique_dates = set()
	for batch, orders_on_same_day in enumerate(orders):
		# pre-process orders
		order_indexes = {} # site,product->[order index->demand]
		demands = [] # a deep copy of demand for each order
		all_supplies = {} # date->{site,product->quantity}
		for idx, (customer, product, demand) in enumerate(orders_on_same_day):
			demands.append(demand)
			for site in sourcing_map.get((customer, product), []):
				supplies = supply_map.get((site, product))
				if supplies is not None:
					for date, quantity in supplies.items():
						all_supplies.setdefault(date, {})
						all_supplies[date][(site,product)] = quantity
					order_indexes.setdefault((site, product), [])
					order_indexes[(site, product)].append(idx)
		supply_dates = list(all_supplies.keys())
		for date in sorted(supply_dates):
			# sort by product, then site alphabetically
			sorted_keys = sorted(all_supplies[date].keys(), key = lambda sorting_key: '_'.join([sorting_key[1], sorting_key[0]]))
			for (site, product) in sorted_keys:
				supply = all_supplies[date][(site, product)]
				claiming_orders = [idx for idx in order_indexes[(site, product)] if demands[idx] > 0]
				if len(claiming_orders) == 0:
					continue
				unique_dates.add(date)
				total_demand = sum([orders_on_same_day[idx][2] for idx in claiming_orders])
				cnt = 0;
				for idx in claiming_orders:
					cnt += 1
					# if it is the last order claims this supply, cap should be all that was left
					# to avoid leaving 1 because of supply is undivisible between orders
					if cnt == len(claiming_orders):
						cap = supply_map[(site, product)][date]
					else:
						cap = orders_on_same_day[idx][2] * supply // total_demand
					fullfilment = min(demands[idx], cap)
					demands[idx] -= fullfilment
					customer = orders_on_same_day[idx][0]
					results.setdefault((batch, idx, site, customer, product), [])
					results[(batch, idx, site, customer, product)].append((date, fullfilment))
					supply_map[(site, product)][date] -= fullfilment
					#print((batch, idx, customer, product, orders_on_same_day[idx][2], demands[(site, product)][idx], supply, supply_map[(site, product)][date], total_demand, cap, ))
					if supply_map[(site, product)][date] == 0:
						del supply_map[(site, product)][date]
						if len(supply_map[(site, product)]) == 0:
							del supply_map[(site, product)]
	# pivot result to readable format
	plan = []
	sorted_dates = sorted(list(unique_dates))
	header = ['site', 'customer', 'product']
	header.extend(sorted_dates)
	plan.append(header)
	# sort result by processing date, then site alphabetically
	sorted_keys = sorted(list(results.keys()), key = lambda sorting_key: '_'.join([str(sorting_key[0]), str(sorting_key[1]), sorting_key[2]]))
	for key in sorted_keys:
		(_batch, _idx, site, customer, product) = key
		fullfilments = results[key]
		row = [site, customer, product]
		row.extend(['' for _i in range(len(sorted_dates))])
		for (date, fullfilment) in fullfilments:
			idx = header.index(date)
			row[idx] = fullfilment
		plan.append(row)
	return plan

def writePlanFile(plan):
	with open('uploads/order_execution_plan.csv', 'w', newline='') as csvfile:
		writer = csv.writer(csvfile)
		for row in plan:
			writer.writerow(row)

def readOrderFile():
	orders = {}
	indexes = {}
	has_error = False
	with open('uploads/order_file.csv', newline='') as f:
		reader = csv.reader(f)
		header_row = next(reader)
		length = len(header_row)
		for header in FILE_HEADERS['order_file']:
			for idx, col in enumerate(header_row):
				if col.lower() == header:
					indexes[header] = idx
			if header not in indexes:
				flash('Demand order file: missing %s column' % header)
				return None
		line_num = 1 
		for row in reader:
			line_num += 1
			if len(row) != length:
				flash('Demand order file, line %d: too many or too few columns' % line_num)
				has_error = True
				continue
			demand = parseQuantity(row[indexes['quantity']])
			if demand is None:
				flash('Demand order file, line %d: cannot parse quantity' % line_num)
				has_error = True
				demand = 0
			order_date = convertDate(row[indexes['date']])
			if order_date is None:
				flash('Demand order file, line %d: cannot parse date' %line_num)
				has_error = True
				order_date = ''
			if demand <= 0:
				continue
			order_list = orders.setdefault(order_date, [])
			order_list.append((row[indexes['customer']], row[indexes['product']], demand))
	if has_error:
		return None
	# sort order by date, then by customer and product alphabetically	
	keys = list(orders.keys())
	keys.sort()
	return [sorted(orders[key], key=lambda row: '-'.join([row[0], row[1]])) for key in keys]

def readSourcingFile():
	# customer,product->[sites]
	sourcing_map = {}
	indexes = {}
	has_error = False
	with open('uploads/sourcing_file.csv', newline='') as f:
		reader = csv.reader(f)
		header_row = next(reader)
		length = len(header_row)
		for header in FILE_HEADERS['sourcing_file']:
			for idx, col in enumerate(header_row):
				if col.lower() == header:
					indexes[header] = idx
			if header not in indexes:
				flash('Sourcing rule file: missing %s column' % header)
				return None
		line_num = 1 
		for row in reader:
			line_num += 1
			if len(row) != length:
				flash('Sourcing rule file, line %d: too many or too few columns' % line_num)
				has_error = True
				continue
			customer = row[indexes['customer']]
			product = row[indexes['product']]
			sites = sourcing_map.setdefault((customer,product), [])
			sites.append(row[indexes['site']])
	if has_error:
		return None
	return sourcing_map

def readSupplyFile():
	# site,product->{date->quantity}
	supply_map = {}
	indexes = {}
	has_error = False
	with open('uploads/supply_file.csv', newline='') as f:
		reader = csv.reader(f)
		header_row = next(reader)
		length = len(header_row)
		for header in FILE_HEADERS['supply_file']:
			for idx, col in enumerate(header_row):
				if col.lower() == header:
					indexes[header] = idx
			if header not in indexes:
				flash('Supply file: missing %s column' % header)
				return None
		line_num = 1 
		for row in reader:
			line_num += 1
			if len(row) != length:
				flash('Supply  file, line %d: too many or too few columns' % line_num)
				has_error = True
				continue
			quantity = parseQuantity(row[indexes['quantity']])
			if quantity is None:
				flash('Supply  file, line %d: cannot parse quantity' % line_num)
				has_error = True
				quantity = 0
			supply_date = convertDate(row[indexes['date']])
			if supply_date is None:
				flash('Supply  file, line %d: cannot parse date' %line_num)
				has_error = True
				supply_date = ''
			if quantity <= 0:
				continue
			site = row[indexes['site']]
			product = row[indexes['product']]
			supply_dict = supply_map.setdefault((site, product), {})
			supply_dict.setdefault(supply_date, 0)
			supply_dict[supply_date] += quantity
	if has_error:
		return None
	return supply_map

def parseQuantity(quantity_str):
	try:
		quantity = int(quantity_str)
	except ValueError:
		return None
	return quantity

def convertDate(date_str):
	try:
		dt = datetime.strptime(date_str, '%d-%b-%y')
	except ValueError:
		try:
			dt = datetime.strptime(date_str, '%d/%m/%y')
		except ValueError:
			try:
				dt = datetime.strptime(date_str, '%Y-%m-%d')
			except ValueError:
				return None
	return dt.strftime('%Y-%m-%d')
	
	