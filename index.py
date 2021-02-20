from datetime import datetime
from flask import Flask
from flask import flash, redirect, render_template, request, send_from_directory, url_for
import copy
import csv
import time

ALLOWED_EXTENSIONS = {'csv'}

app = Flask(__name__)
app.config['SECRET_KEY'] = '123456'

@app.route('/', methods=['GET', 'POST'])
def index():
	if request.method == 'POST':
		# check if the post request has the file part
		file_names = ['order_file', 'supply_file', 'sourcing_file']
		has_error = False
		for file_name in file_names:
			has_error = check_file(file_name, request.files) or has_error
		if has_error:
			return redirect(url_for('index'))
		return redirect(url_for('plan'))

	return render_template('index.html')

def check_file(file_name, files):
	if file_name not in request.files:
		flash(file_name + ' is not uploaded')
		return True
	file = files[file_name]
	# if user does not select file, browser also
	# submit an empty part without filename
	if file.filename == '' or file is None:
		flash(file_name + ' is not uploaded')
		return True
	if not allowed_file(file.filename):
		flash('The format for file ' + file.filename + ' is not supported')
		return True
	file.save('uploads/' + file_name + '.csv')
	return False

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/plan')
def plan():
	allocate()
	return render_template('plan.html')

@app.route('/download', methods=['GET'])
def download():
	return send_from_directory('uploads/', 'order_execution_plan.csv', as_attachment=True)

def allocate():
	orders = readOrderFile()
	sourcing_map = readSourcingFile()
	supply_map = readSupplyFile()
	# allocate
	results = []
	unique_dates = set()
	for orders_on_same_day in orders:
		# pre-process orders
		# calculate all claims to supply for site, product combinations on same day
		total_demand = {} # site,product->total demand from all orders can source from this site
		order_set = {} # site,product->{date->order index}
		all_supply_keys = [[] for _i in range(len(orders_on_same_day))] # list of [site,product combinations]
		for idx, (customer, product, demand) in enumerate(orders_on_same_day):
			sites = sourcing_map.get((customer, product), [])
			for site in sites:
				supplies = supply_map.get((site, product))
				if supplies is not None:
					for date in supplies.keys():
						order_set.setdefault((site, product), {})
						order_set[(site, product)].setdefault(date, set())
						order_set[(site, product)][date].add(idx)
					total_demand.setdefault((site, product), 0)
					total_demand[(site, product)] += demand
					all_supply_keys[idx].append((site, product))
		tmp_supply_map = copy.deepcopy(supply_map)
		for idx, (customer, product, demand) in enumerate(orders_on_same_day):
			if len(all_supply_keys[idx]) == 0:
				continue
			order_supplies = []
			for (site, product) in all_supply_keys[idx]:
				supplies = tmp_supply_map[(site, product)]
				for date, quantity in supplies.items():
					order_supplies.append((date, quantity, site))
			# sort by date, then site alphabetically
			order_supplies = sorted(order_supplies, key=lambda supply: '-'.join([supply[0], supply[2]]))
			fullfilments = {}
			origin_demand = demand
			for (date, supply, site) in order_supplies:
				# if it is the last order claims this supply, cap should be all that was left
				# to avoid leaving 1 because of supply is undivisible between orders
				if demand > 0:
					if len(order_set[(site, product)][date]) == 1:
						cap = supply_map[(site, product)][date]
					else:
						cap = origin_demand * supply // total_demand[(site, product)]
					fullfillment = min(demand, cap)
					demand -= fullfillment
					fullfilments.setdefault(site, [])
					fullfilments[site].append((date, fullfillment))
					supply_map[(site, product)][date] -= fullfillment
					if supply_map[(site, product)][date] == 0:
						del supply_map[(site, product)][date]
						if len(supply_map[(site, product)]) == 0:
							del supply_map[(site, product)]
					unique_dates.add(date)
				order_set[(site, product)][date].discard(idx)				
			results.append((customer, product, fullfilments))

	# write to result csv 
	sorted_dates = sorted(list(unique_dates))
	with open('uploads/order_execution_plan.csv', 'w', newline='') as csvfile:
		writer = csv.writer(csvfile)
		header = ['site', 'customer', 'product']
		header.extend(sorted_dates)
		writer.writerow(header)
		for result in results:
			for site, site_fullfilments in result[2].items():
				row = [site, result[0], result[1],]
				row.extend(['' for _i in range(len(sorted_dates))])
				for fullfillment in site_fullfilments:
					idx = header.index(fullfillment[0])
					row[idx] = fullfillment[1]
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
	return [sorted(orders[key], key=lambda row: '-'.join([row[1], row[0]])) for key in keys]

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









