from flask import Flask
from flask import flash, redirect, render_template, request, send_from_directory, url_for

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
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/plan')
def plan():
	return render_template('plan.html')

@app.route("/download", methods=['GET'])
def download():
	return send_from_directory('uploads/', 'order_file.csv', as_attachment=True)