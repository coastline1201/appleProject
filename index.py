from datetime import datetime
from flask import Flask
from flask import flash, redirect, render_template, request, send_from_directory, url_for
import copy
import csv
import os
import time

ALLOWED_EXTENSIONS = {'csv'}
FILE_NAMES = ['order_file', 'supply_file', 'sourcing_file']

app = Flask(__name__)
app.config['SECRET_KEY'] = '123456'

@app.route('/', methods=['GET', 'POST'])
def index():
	has_file = {}
	for file_name in FILE_NAMES:
		has_file[file_name] = os.path.isfile('uploads/' + file_name + '.csv')

	if request.method == 'POST':
		# check if the post request has the file part
		has_error = False
		for file_name in FILE_NAMES:
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
	with open('uploads/order_file.csv', newline='') as f:
		reader = csv.reader(f)
		# header row is not used
		next(reader)
		for row in reader:
			demand = int(row[3])
			if demand <= 0:
				continue
			order_date = convertDate(row[2], '%d-%b-%y')
			orders.setdefault(order_date, [])
			orders[order_date].append((row[0], row[1], demand)) # customer, product, quantity
	# sort order by date, then by customer and product alphabetically	
	keys = list(orders.keys())
	keys.sort()
	return [sorted(orders[key], key=lambda row: '-'.join([row[0], row[1]])) for key in keys]

def readSourcingFile():
	# customer,product->[sites]
	sourcing_map = dict()
	with open('uploads/sourcing_file.csv', newline='') as f:
		reader = csv.reader(f)
		# header row is not used
		next(reader)
		for row in reader:
			sourcing_key = tuple(row[1:]) # customer,product
			sourcing_map.setdefault(sourcing_key, [])
			sourcing_map[sourcing_key].append(row[0]) # site
	return sourcing_map

def readSupplyFile():
	# site,product->{date->quantity}
	supply_map = dict()
	with open('uploads/supply_file.csv', newline='') as f:
		reader = csv.reader(f)
		# header row is not used
		next(reader)
		for row in reader:
			quantity = int(row[3])
			if quantity <= 0:
				continue
			supply_key = tuple(row[0:2]) # site,product
			supply_map.setdefault(supply_key, {})
			supply_date = convertDate(row[2], '%d/%m/%y')
			supply_map[supply_key].setdefault(supply_date, 0)
			supply_map[supply_key][supply_date] += quantity
	return supply_map

def convertDate(date_str, pattern):
	dt = datetime.strptime(date_str, pattern)
	return dt.strftime('%Y-%m-%d')









