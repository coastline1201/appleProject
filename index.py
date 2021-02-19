from datetime import datetime
from flask import Flask
from flask import flash, redirect, render_template, request, send_from_directory, url_for
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
	for order in orders:
		customer = order[0]
		product = order[1]
		demand = int(order[3])
		if demand <= 0:
			continue
		sites = sourcing_map.get((customer, product))
		if sites is None:
			continue
		all_supplies = []
		for site in sites:
			supplies = supply_map.get((site, product))
			if supplies is None:
				continue
			for date, quantity in supplies.items():
				all_supplies.append((date, quantity, site))
		if len(all_supplies) == 0:
			continue
		# sort by date, then site alphabetically
		all_supplies = sorted(all_supplies, key=lambda supply: '-'.join([supply[0], supply[2]]))
		fullfilments = {}
		for i in range(len(all_supplies)):
			(date, supply, site) = all_supplies[i]
			if supply == 0:
				continue
			fullfillment = min(demand, supply)
			demand = demand - fullfillment
			supply = supply - fullfillment
			site_fullfilments = fullfilments.get(site, [])
			site_fullfilments.append((date, fullfillment))
			fullfilments[site] = site_fullfilments
			if supply == 0:
				del supply_map[(site, product)][date]
				if len(supply_map[(site, product)]) == 0:
					del supply_map[(site, product)]
			else:
				supply_map[(site, product)][date] = supply
			unique_dates.add(date)
			if (demand == 0):
				break
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
	orders = []
	with open('uploads/order_file.csv', newline='') as f:
		reader = csv.reader(f)
		# header row is not used
		next(reader)
		for row in reader:
			row[2] = convertDate(row[2], '%d-%b-%y')
			orders.append(row)
	# sort order by date, then by customer and product alphabetically	
	return sorted(orders, key=lambda row: '-'.join([row[2], row[1], row[0]]))

def readSourcingFile():
	# customer,product->[sites]
	sourcing_map = dict()
	with open('uploads/sourcing_file.csv', newline='') as f:
		reader = csv.reader(f)
		# header row is not used
		next(reader)
		for row in reader:
			sourcing_key = tuple(row[1:]) # customer,product
			sourcing_value = sourcing_map.get(sourcing_key, [])
			sourcing_value.append(row[0]) # site
			sourcing_map[sourcing_key] = sourcing_value
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
			if (quantity <= 0):
				continue
			supply_key = tuple(row[0:2]) # site,product
			supply_value = supply_map.get(supply_key, {})
			supply_date = convertDate(row[2], '%d/%m/%y')
			supply_quantity = supply_value.get(supply_date, 0)
			supply_value[supply_date] = supply_quantity + quantity
			supply_map[supply_key] = supply_value
	return supply_map

def convertDate(date_str, pattern):
	dt = datetime.strptime(date_str, pattern)
	return dt.strftime('%Y-%m-%d')









