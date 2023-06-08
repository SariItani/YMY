import calendar
import csv
from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from sqlalchemy import and_, inspect, extract, func
from .models import *
from . import db
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import urllib.parse
import zipfile
from twilio.rest import Client

account_sid = 'your sid'
auth_token = 'your token'
twilio_phone_number = '+your twilio number'

client = Client(account_sid, auth_token)


views = Blueprint('views', __name__)

current_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_path)
relative_upload_folder = 'projects'
UPLOAD_FOLDER = os.path.join(current_directory, relative_upload_folder)
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'xlsx', 'xls', 'pptx', 'ppt',
                      'odt', 'odf', 'ods', 'zip', '7z', 'png', 'jpg', 'csv', 'tsv', 'html', 'jpeg', 'gif', 'js', 'py'}


def send_whatsapp_message(to_phone_number, message, file_path=None):
    message_data = {
        'body': message,
        'from_': f'whatsapp:{twilio_phone_number}',
        'to': f'whatsapp:+{to_phone_number}'
    }
    print(message_data)
    if file_path:
        media_data = {
            'media_url': file_path
        }
        message_data.update(media_data)
    return client.messages.create(**message_data)


def add_department(department):
    existing_departments = set()
    try:
        with open('departments.csv', 'r', newline='') as file:
            reader = csv.reader(file)
            existing_departments = set(row[0] for row in reader)
    except FileNotFoundError:
        pass
    existing_departments.add(department.lower())
    with open('departments.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows([[dep] for dep in existing_departments])


def get_departments():
    try:
        with open('departments.csv', 'r', newline='') as file:
            reader = csv.reader(file)
            return [row[0] for row in reader]
    except FileNotFoundError:
        return []


def convert(value, data_type):
    if value:
        if data_type == int:
            return int(value)
        elif data_type == str:
            return str(value)
        elif data_type == datetime:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        elif data_type == float:
            if value.lower() == 'none':
                return None
            else:
                return float(value)
        elif data_type == bool:
            if value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
            else:
                raise ValueError(f"Invalid boolean value: {value}")
        elif data_type is None:
            return None
    return None


def get_modified_results(results, headers, objects):
    modified_results = []
    for row in results:
        modified_row = {}
        for header in headers:
            cell = getattr(row, header)
            if cell is not None:
                if header == 'tutors_received':
                    tutor_ids = json.loads(cell) if cell else []
                    tutor_names = []
                    for tutor_id in tutor_ids:
                        tutor = Tutors.query.get(tutor_id)
                        if tutor is not None:
                            tutor_names.append(
                                f"{tutor.name} (ID: {tutor.id})")
                    modified_row[header] = ', '.join(tutor_names)
                elif header == 'projects':
                    project_names = []
                    for project in cell:
                        if project.status != 'Complete':
                            project_names.append(
                                f"{project.name} (ID: {project.id})")
                    modified_row[header] = ', '.join(project_names)
                elif header in objects:
                    if isinstance(cell, list):
                        modified_row[header] = ', '.join(
                            f'{item.name} ({item.id})' for item in cell)
                    else:
                        modified_row[header] = f'{cell.name} (ID: {cell.id})'
                else:
                    modified_row[header] = cell
            else:
                modified_row[header] = "None"
        modified_results.append(modified_row)
    return modified_results


def get_js_time(datetime_obj):
    return datetime.strptime(datetime_obj.strftime('%Y-%m-%dT%H:%M:%S'), '%Y-%m-%dT%H:%M:%S')


@views.route('/', methods=["POST", "GET"])
@login_required
def home():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
    return render_template("/home.html")


@views.route('/departments-table', methods=['POST', 'GET'])
@login_required
def departments_table():
    departments = set()
    incomplete_projects = Projects.query.filter(
        Projects.status != 'Complete').all()
    tutor_client_dict = {}
    with open('departments.csv', 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            departments.add(row[0].strip())
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('query_type'):
            selected_department = request.form.get('query_type')
            department_tutors = Tutors.query.filter_by(
                department=selected_department).all()
            tutor_name_id = [
                f"{tutor.name} (ID: {tutor.id})" for tutor in department_tutors]
            projects = [
                project for project in incomplete_projects if project.department == selected_department]
            tutor_client_dict = {}
            for t in tutor_name_id:
                tutor_client_dict[t] = []
            for tutor in department_tutors:
                tutor_id = tutor.id
                for project in projects:
                    if project.tutor_id == tutor_id:
                        client_name_id = f"{project.client_name}"
                        tutor_name_id = f"{tutor.name} (ID: {tutor.id})"
                        tutor_client_dict[tutor_name_id].append(client_name_id)
            return render_template("/departments-table.html", departments=departments, tutor_client_dict=tutor_client_dict)
    return render_template("/departments-table.html", departments=departments)


@views.route('/pending-table', methods=["POST", "GET"])
@login_required
def pending_table():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('task') == 'task':
            name = request.form.get('name')
            type = request.form.get('type')
            university = request.form.get('university').upper()
            department = request.form.get('dpt').lower()
            due_str = request.form.get('due')
            due = datetime.strptime(due_str, '%Y-%m-%dT%H:%M')
            price = float(request.form.get('price'))
            description = request.form.get('description')
            client_name = request.form.get('client').lower()
            project = Projects(name=name, type=type, department=department, due=due, price=price,
                               description=description, client_name=client_name, status='pending', university=university)
            db.session.add(project)
            db.session.commit()
            files = request.files.getlist('file[]')
            if any(files):
                directory = os.path.join(
                    'projects', department, f"{name}_{project.id}")
                os.makedirs(directory, exist_ok=True)
                for file in files:
                    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                        filename = secure_filename(file.filename)
                        path = os.path.join(directory, filename)
                        file.save(path)
                zip_filename = f"{name}_{project.id}.zip"
                zip_path = os.path.join(directory, zip_filename)
                with zipfile.ZipFile(zip_path, 'w') as zip_file:
                    for file in files:
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(directory, filename)
                        zip_file.write(file_path, filename)
                project.fileClient = zip_path
                db.session.commit()
                for file in files:
                    os.remove(os.path.join(
                        directory, secure_filename(file.filename)))
        elif request.form.get('send-to-tutor'):
            project_id = request.form.get('send-to-tutor')
            print(project_id)
            tutor_id = request.form.get(f'tutor-id-{project_id}')
            print(tutor_id)
            if tutor_id != "all":
                project = Projects.query.get(project_id)
                project.at_tutor = datetime.utcnow()
                project.status = "In-Progress"
                project.tutor_id = tutor_id
                expected_due = request.form.get(f'expected-due-{project.id}')
                if expected_due:
                    project.expected_due = datetime.strptime(
                        expected_due, '%Y-%m-%d %H:%M')
                print(project_id, tutor_id, project.at_tutor, project.tutor_id,
                      project.status, "Expected-Due:", expected_due)
                db.session.commit()
        elif request.form.get('whatsapp'):
            project_id = request.form.get('whatsapp')
            tutor_phone = request.form.get(f'tutor-phone-{project_id}')
            project = Projects.query.get(project_id)
            tutor_id = request.form.get(f'tutor-id-{project_id}')
            if tutor_id == "all":
                tutor_phone = set()
                department = project.department
                all_tutors = Tutors.query.filter_by(department=department)
                for each in all_tutors:
                    project.add_tutor_received(each.id)
                    tutor_phone.add(each.number)
            else:
                tutor_phone = set([tutor_phone])
                project.add_tutor_received(int(tutor_id))
            db.session.commit()
            file_path = project.fileClient
            message = f"Can you please do {project.name}?"
            for phone in tutor_phone:
                send_whatsapp_message(phone, message)
            print(tutor_phone, message, file_path)
    pending_table = Projects.query.filter_by(status='pending').all()
    for project in pending_table:
        project.created_at = get_js_time(project.created_at)
    tutors = Tutors.query.all()
    return render_template("/pending_table.html", pending_table=pending_table, tutors=tutors, departments=get_departments())


@views.route('/progress-table', methods=['POST', 'GET'])
@login_required
def progress_table():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif 'dismiss' in request.form:
            projectId = request.form['dismiss']
            project = Projects.query.get(projectId)
            project.status = 'pending'
            project.tutor_id = None
            project.at_tutor = None
            project.expected_due = None
            db.session.commit()
        elif 'complete' in request.form:
            projectId = request.form['complete']
            project = Projects.query.get(projectId)
            project.status = 'Complete'
            files = request.files.getlist(f'tutor-file-{projectId}[]')
            print(f'tutor-file-{projectId}[]')
            print("FILES", files)
            gain = request.form.get(f'gain-{projectId}')
            project.gain = gain
            project.at_client = datetime.utcnow()
            db.session.commit()
            if any(files):
                print("I received files...")
                directory = os.path.join(
                    'tutor-projects', project.department, f"{project.name}_{project.id}")
                os.makedirs(directory, exist_ok=True)
                print("i am making a directory...")
                for file in files:
                    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                        filename = secure_filename(file.filename)
                        path = os.path.join(directory, filename)
                        file.save(path)
                        print(f"I added {filename}...")
                zip_filename = f"{project.name}_{project.id}.zip"
                print(f"I am creating the zip file {zip_filename}...")
                zip_path = os.path.join(directory, zip_filename)
                with zipfile.ZipFile(zip_path, 'w') as zip_file:
                    for file in files:
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(directory, filename)
                        zip_file.write(file_path, filename)
                        os.remove(file_path)
                project.fileTutor = zip_path
                db.session.commit()
    progress_table = Projects.query.filter_by(status='In-Progress').all()
    tutor_ids = [project.tutor_id for project in progress_table]
    tutors = Tutors.query.filter(Tutors.id.in_(tutor_ids)).all()
    client_names = {}
    projects = Projects.query.all()
    project_client_dict = {}
    for project in projects:
        project_client_dict[project.id] = client_names.get(
            project.client_name, '')
    return render_template("/progress_table.html", progress_table=progress_table, tutors=tutors, project_client_dict=project_client_dict)


@views.route('/reports', methods=["POST", "GET"])
@login_required
def reports():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('query_type'):
            query_type = request.form.get('query_type')
            if query_type == 'month':
                months_data = db.session.query(db.func.extract(
                    'month', Projects.at_client)).distinct().all()
                monthly_data = {}
                for month_tuple in months_data:
                    month_number = month_tuple[0]
                    if month_number:
                        month_name = calendar.month_name[month_number]
                        month_projects = Projects.query.filter(db.func.extract(
                            'month', Projects.at_client) == month_number).all()
                        revenue = 0
                        tutor_count = 0
                        client_count = 0
                        university_count = 0
                        department_data = set()
                        tutor_ids = set()
                        client_ids = set()
                        university_names = set()
                        for project in month_projects:
                            if project.price and project.gain:
                                revenue += project.price - project.gain
                            tutor_ids.add(project.tutor_id)
                            client_ids.add(project.client_name)
                            if project.university is not None:
                                university_names.add(project.university)
                            department_data.add(project.department)
                        tutor_count = len(tutor_ids)
                        client_count = len(client_ids)
                        university_count = len(university_names)
                        department_count = len(department_data)
                        monthly_data[month_name] = {
                            'Revenue': revenue,
                            'Tutor Count': tutor_count,
                            'Client Count': client_count,
                            'University Count': university_count,
                            'Department Count': department_count
                        }
                headers = list(next(iter(monthly_data.values())
                                    ).keys()) if monthly_data else ['Month']
                headers.insert(0, 'Month')
                return render_template("/reports.html", query_type=query_type, data=monthly_data, headers=headers)
            elif query_type == 'department':
                department_names = []
                with open('departments.csv', 'r') as csvfile:
                    reader = csv.reader(csvfile)
                    department_names = [row[0] for row in reader]
                department_data = {}
                for department_name in department_names:
                    department_projects = Projects.query.filter_by(
                        department=department_name).all()
                    department_projects = [
                        project for project in department_projects if project.status == "Complete"]
                    revenue = 0
                    tutor_count = 0
                    client_count = 0
                    university_count = 0
                    project_count = len(department_projects)
                    tutor_ids = set()
                    client_ids = set()
                    university_names = set()
                    for project in department_projects:
                        if project.gain and project.price:
                            revenue += project.price - project.gain
                        tutor_ids.add(project.tutor_id)
                        client_ids.add(project.client_name)
                        university_names.add(project.university)
                    tutor_count = len(tutor_ids)
                    client_count = len(client_ids)
                    university_count = len(university_names)
                    department_data[department_name] = {
                        'Revenue': revenue,
                        'Tutor Count': tutor_count,
                        'Client Count': client_count,
                        'University Count': university_count,
                        'Project Count': project_count
                    }
                headers = list(next(iter(department_data.values())).keys(
                )) if department_data else ['Department']
                headers.insert(0, 'Department')
                return render_template("/reports.html", query_type=query_type, data=department_data, headers=headers)
            elif query_type == 'uni':
                universities_data = db.session.query(
                    Projects.university).distinct().all()
                university_data = {}
                for university_tuple in universities_data:
                    university_name = university_tuple[0]
                    university_projects = Projects.query.filter_by(
                        university=university_name, status='Complete').all()
                    revenue = 0
                    tutor_count = 0
                    client_count = 0
                    project_count = len(university_projects)
                    department_summary = set()
                    tutor_ids = set()
                    client_ids = set()
                    for project in university_projects:
                        if project.price and project.gain:
                            revenue += project.price - project.gain
                        tutor_ids.add(project.tutor_id)
                        client_ids.add(project.client_name)
                        department_summary.add(project.department)
                    tutor_count = len(tutor_ids)
                    client_count = len(client_ids)
                    university_data[university_name] = {
                        'Revenue': revenue,
                        'Tutor Count': tutor_count,
                        'Client Count': client_count,
                        'Project Count': project_count,
                        'Department Count': len(department_summary)
                    }
                headers = list(next(iter(university_data.values())).keys(
                )) if university_data else ['University']
                headers.insert(0, 'University')
                return render_template("/reports.html", query_type=query_type, data=university_data, headers=headers)
    return render_template("/reports.html")


@views.route('/download/<path:filepath>', methods=['GET'])
@login_required
def download_file(filepath):
    filepath = urllib.parse.unquote(filepath)
    absolute_filepath = os.path.abspath(filepath)
    if os.path.exists(absolute_filepath):
        return send_file(absolute_filepath, as_attachment=True)
    else:
        return "File not found."


@views.route('/entries', methods=['POST', 'GET'])
@login_required
def entries():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('department') == 'department':
            department_name = request.form.get('name').lower()
            add_department(department_name)
            print(department_name)
            departments_list = get_departments()
            print("Departments list:", departments_list)
        elif request.form.get('tutor') == 'tutor':
            name = request.form.get('name')
            department = request.form.get('dpt').lower()
            number = request.form.get('number')
            email = request.form.get('email')
            tutor = Tutors(name=name, department=department,
                           email=email, number=number)
            db.session.add(tutor)
            db.session.commit()
    return render_template("/entries.html", departments=get_departments())


@views.route('/search', methods=['POST', 'GET'])
@login_required
def search():
    tutors = Tutors.query.all()
    if request.method == 'POST':
        objects = ['client', 'tutor', 'projects']
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('tutor') == 'tutor':
            search_query_name = request.form.get('name').strip()
            search_query_department = request.form.get('department').strip()
            search_query_number = request.form.get('number').strip()
            tutors_filtered = Tutors.query.filter(
                and_(Tutors.name.ilike(f'%{search_query_name}%'),
                     Tutors.department.ilike(f'%{search_query_department}%'),
                     Tutors.number.ilike(f'%{search_query_number}%')
                     )
            ).all()
            results = tutors_filtered
            headers = list(Tutors.__mapper__.columns.keys()) + \
                list(Tutors.__mapper__.relationships.keys())
            headers = [header for header in headers if header not in [
                'tutor_id', 'client_id']]
            modified_results = get_modified_results(results, headers, objects)
            return render_template("search.html", results=modified_results, headers=headers, departments=get_departments(), tutors=tutors)
        elif request.form.get('project') == 'project':
            search_query_name = request.form.get('name').strip()
            search_query_type = request.form.get('type').strip()
            search_query_status = request.form.get('status').strip()
            search_query_department = request.form.get('department').strip()
            search_query_due_str = request.form.get('due').strip()
            projects_filtered = Projects.query.filter(
                and_(Projects.name.ilike(f'%{search_query_name}%'),
                     Projects.department.ilike(f'%{search_query_department}%'),
                     Projects.due.ilike(f'%{search_query_due_str}%'),
                     Projects.status.ilike(f'%{search_query_status}%'),
                     Projects.type.ilike(f'%{search_query_type}%')
                     )
            ).all()
            results = projects_filtered
            headers = list(Projects.__mapper__.columns.keys()) + \
                list(Projects.__mapper__.relationships.keys())
            headers = [header for header in headers if header not in [
                'tutor_id', 'client_id']]
            modified_results = get_modified_results(results, headers, objects)
            return render_template("search.html", results=modified_results, headers=headers, departments=get_departments(), tutors=tutors)
        elif request.form.get('save') == 'save':
            form_headers = request.form.get('headers')
            if form_headers:
                form_headers = form_headers.split(',')
            headers_map = {
                tuple(header for header in list(Projects.__mapper__.columns.keys()) + list(Projects.__mapper__.relationships.keys()) if header not in ['tutor_id', 'client_id']): 'projects',
                tuple(header for header in list(Tutors.__mapper__.columns.keys()) + list(Tutors.__mapper__.relationships.keys()) if header not in ['tutor_id', 'client_id']): 'tutors'
            }
            table = headers_map.get(tuple(form_headers), None)
            if table:
                table_mapping = {
                    'projects': Projects,
                    'tutors': Tutors,
                }
                table_class = table_mapping.get(table)
                data = {}
                for header in form_headers:
                    values = request.form.getlist(header + '[]')
                    data[header] = values
                name_values = data.get('id')
                if name_values:
                    id_values = []
                    for value in name_values:
                        id_value = value.split('-')[-1]
                        id_values.append(id_value)
                    for id_value in id_values:
                        record = table_class.query.get(id_value)
                        if record:
                            for header in ['name', 'department', 'description', 'due', 'price', 'client_id', 'university', 'number', 'email', 'gain']:
                                try:
                                    original_value = data[header][int(
                                        id_value) - 1]
                                    mapper = inspect(table_class)
                                    column_property = mapper.attrs.get(header)
                                    data_type = column_property.columns[0].type.python_type
                                    converted_value = convert(
                                        original_value, data_type)
                                    setattr(record, header, converted_value)
                                except KeyError:
                                    pass
                            db.session.commit()
    return render_template("search.html", departments=get_departments(), tutors=tutors)
