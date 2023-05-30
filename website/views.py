from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from sqlalchemy import and_, inspect, extract, func
from .models import *
from . import db
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import urllib.parse

views = Blueprint('views', __name__)

current_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_path)
relative_upload_folder = 'projects'
UPLOAD_FOLDER = os.path.join(current_directory, relative_upload_folder)
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'xlsx', 'pptx',
                      'odt', 'odf', 'ods', 'zip', '7z', 'png', 'jpg', 'csv', 'tsv'}


def convert(value, data_type):
    """
    Convert the value to the specified data type.
    Add additional conversion logic as needed.
    """
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
                if header in objects:
                    if isinstance(cell, list):
                        modified_row[header] = ', '.join(
                            f'{item.id}_{item.name}' for item in cell)
                    else:
                        modified_row[header] = f'{cell.id}_{cell.name}'
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


@views.route('/pending-table', methods=["POST", "GET"])
@login_required
def pending_table():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('send-to-tutor'):
            project_id = request.form.get('send-to-tutor')
            project = Projects.query.get(project_id)
            project.at_tutor = datetime.utcnow()
            project.status = "In-Progress"
            tutor_id = request.form.get(f'tutor-id-{project_id}')
            project.tutor_id = tutor_id
            db.session.commit()
        elif request.form.get('whatsapp'):
            project_id=request.form.get('whatsapp')
            tutor_phone = request.form.get(f'tutor-phone-{project_id}')
    pending_table = Projects.query.filter_by(status='pending').all()
    for project in pending_table:
        project.created_at = get_js_time(project.created_at)
    tutors = Tutors.query.all()
    return render_template("/pending_table.html", pending_table=pending_table, tutors=tutors)


@views.route('/progress-table', methods=['POST', 'GET'])
@login_required
def progress_table():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('complete'):
            projectId = request.form.get('complete')
            project = Projects.query.get(projectId)
            project.status='Complete'
            file = request.files.get(f'tutor-file-{projectId}')
            gain=request.form.get(f'gain-{projectId}')
            project.gain=gain
            project.at_client=datetime.utcnow()
            db.session.commit()
            if file:
                if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                    filename = secure_filename(file.filename)
                    path = os.path.join(
                        'tutor-projects', project.department, f"{project.name}_{projectId}", filename)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    file.save(path)
                    project.fileTutor = path
                    db.session.commit()
    progress_table = Projects.query.filter_by(status='In-Progress').all()
    tutor_ids = [project.tutor_id for project in progress_table]
    tutors = Tutors.query.filter(Tutors.id.in_(tutor_ids)).all()
    return render_template("/progress_table.html", progress_table=progress_table, tutors=tutors)


@views.route('/reports', methods=["POST", "GET"])
@login_required
def reports():
    if request.method == 'POST':
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('query_type'):
            query_type = request.form.get('query_type')
            if query_type == 'month':
                months_data = db.session.query(func.extract('month', Projects.at_client)).distinct().all()
                monthly_data = {}
                for month_tuple in months_data:
                    month_number = month_tuple[0]
                    month_projects = Projects.query.filter(func.extract('month', Projects.at_client) == month_number).all()
                    revenue = 0
                    tutor_data = []
                    client_data = []
                    university_data = []
                    department_data = []
                    for project in month_projects:
                        revenue += project.price - project.gain
                        tutor_name_id = f"{project.tutor.name} (ID: {project.tutor.id})"
                        tutor_data.append(tutor_name_id)
                        client_name_id = f"{project.client.name} (ID: {project.client.id})"
                        client_data.append(client_name_id)
                        university_data.append(project.client.university)
                        department_data.append(project.department)
                    monthly_data[month_number] = {
                        'Revenue': revenue,
                        'Tutors': tutor_data,
                        'Clients': client_data,
                        'Universities': university_data,
                        'Departments': department_data
                    }
                for month_data in monthly_data.values():
                    month_data['Tutors'] = ', '.join(month_data['Tutors'])
                    month_data['Clients'] = ', '.join(month_data['Clients'])
                    month_data['Universities'] = ', '.join(month_data['Universities'])
                    month_data['Departments'] = ', '.join(month_data['Departments'])
                headers = list(next(iter(monthly_data.values())).keys())
                headers.insert(0, 'Month #nb')
                print(headers)
                print(monthly_data)
                return render_template("/reports.html", query_type=query_type, data=monthly_data, headers=headers)
            elif query_type == 'department':
                departments_data = db.session.query(Projects.department).distinct().all()
                department_data = {}
                for department_tuple in departments_data:
                    department_name = department_tuple[0]
                    department_projects = Projects.query.filter_by(department=department_name).all()
                    revenue = 0
                    tutor_data = []
                    client_data = []
                    university_data = []
                    project_data = []
                    for project in department_projects:
                        revenue += project.price - project.gain
                        tutor_name_id = f"{project.tutor.name} (ID: {project.tutor.id})"
                        tutor_data.append(tutor_name_id)
                        client_name_id = f"{project.client.name} (ID: {project.client.id})"
                        client_data.append(client_name_id)
                        university_data.append(project.client.university)
                        project_data.append(project.name)
                    department_data[department_name] = {
                        'Revenue': revenue,
                        'Tutors': ', '.join(tutor_data),
                        'Clients': ', '.join(client_data),
                        'Universities': ', '.join(university_data),
                        'Projects': ', '.join(project_data)
                    }
                headers = list(next(iter(department_data.values())).keys()) if department_data else ['Department']
                headers.insert(0, 'Department')
                return render_template("/reports.html", query_type=query_type, data=department_data, headers=headers)
            elif query_type == 'uni':
                universities_data = db.session.query(Clients.university).distinct().all()
                university_data = {}
                for university_tuple in universities_data:
                    university_name = university_tuple[0]
                    university_projects = Projects.query.join(Clients).filter(Clients.university == university_name).all()
                    revenue = 0
                    tutor_data = []
                    client_data = []
                    department_data = set()
                    project_data = []
                    for project in university_projects:
                        revenue += project.price - project.gain
                        tutor_name_id = f"{project.tutor.name} (ID: {project.tutor.id})"
                        tutor_data.append(tutor_name_id)
                        client_name_id = f"{project.client.name} (ID: {project.client.id})"
                        client_data.append(client_name_id)
                        department_data.add(project.department)  # Use set to collect unique department names
                        project_data.append(project.name)
                    university_data[university_name] = {
                        'Revenue': revenue,
                        'Tutors': ', '.join(tutor_data),
                        'Clients': ', '.join(client_data),
                        'Departments': ', '.join(department_data),
                        'Projects': ', '.join(project_data)
                    }
                headers = ['University', 'Revenue', 'Tutors', 'Clients', 'Departments', 'Projects']
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
        elif request.form.get('client') == 'client':
            name = request.form.get('name')
            university = request.form.get('university').upper()
            department = request.form.get('department').lower()
            number = request.form.get('number')
            email = request.form.get('email')
            client = Clients(name=name, university=university,
                             email=email, department=department, number=number)
            db.session.add(client)
            db.session.commit()
        elif request.form.get('tutor') == 'tutor':
            name = request.form.get('name')
            department = request.form.get('department').lower()
            number = request.form.get('number')
            email = request.form.get('email')
            tutor = Tutors(name=name, department=department,
                           email=email, number=number)
            db.session.add(tutor)
            db.session.commit()
        elif request.form.get('project') == 'project':
            name = request.form.get('name')
            department = request.form.get('department').lower()
            due_str = request.form.get('due')
            due = datetime.strptime(due_str, '%Y-%m-%dT%H:%M')
            price = float(request.form.get('price'))
            description = request.form.get('description')
            client_id = request.form.get('client')
            project = Projects(name=name, department=department, due=due, price=price, description=description, client_id=client_id, status='pending')
            db.session.add(project)
            db.session.commit()
            file = request.files.get('file')
            if file:
                if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                    filename = secure_filename(file.filename)
                    path = os.path.join(
                        'projects', department, f"{name}_{project.id}", filename)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    file.save(path)
                    project.fileClient = path
                    db.session.commit()
    clients = Clients.query.all()
    return render_template("/entries.html", clients=clients)


@views.route('/search', methods=['POST', 'GET'])
@login_required
def search():
    if request.method == 'POST':
        # excluded_headers = ['__module__', '__doc__', '__tablename__', '_sa_class_manager', '__table__', '__init__', '__mapper__', 'tutor_id', 'client_id']
        objects = ['client', 'tutor', 'projects']
        if request.form.get('logout') == 'logout':
            return redirect(url_for('auth.logout'))
        elif request.form.get('client') == 'client':
            search_query_name = request.form.get('name').strip()
            search_query_university = request.form.get('university').strip()
            search_query_department = request.form.get('department').strip()
            search_query_number = request.form.get('number').strip()
            clients_filtered = Clients.query.filter(
                and_(
                    Clients.name.ilike(f'%{search_query_name}%'),
                    Clients.university.ilike(f'%{search_query_university}%'),
                    Clients.department.ilike(f'%{search_query_department}%'),
                    Clients.number.ilike(f'%{search_query_number}%')
                )
            ).all()
            results = clients_filtered
            headers = list(Clients.__mapper__.columns.keys()) + \
                list(Clients.__mapper__.relationships.keys())
            headers = [header for header in headers if header not in [
                'tutor_id', 'client_id']]
            modified_results = get_modified_results(results, headers, objects)
            return render_template("search.html", results=modified_results, headers=headers)
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
            return render_template("search.html", results=modified_results, headers=headers)
        elif request.form.get('project') == 'project':
            search_query_name = request.form.get('name').strip()
            search_query_status = request.form.get('status').strip()
            search_query_department = request.form.get('department').strip()
            search_query_due_str = request.form.get('due').strip()
            projects_filtered = Projects.query.filter(
                and_(Projects.name.ilike(f'%{search_query_name}%'),
                     Projects.department.ilike(f'%{search_query_department}%'),
                     Projects.due.ilike(f'%{search_query_due_str}%'),
                     Projects.status.ilike(f'%{search_query_status}%')
                     )
            ).all()
            results = projects_filtered
            headers = list(Projects.__mapper__.columns.keys()) + \
                list(Projects.__mapper__.relationships.keys())
            headers = [header for header in headers if header not in [
                'tutor_id', 'client_id']]
            modified_results = get_modified_results(results, headers, objects)
            return render_template("search.html", results=modified_results, headers=headers)
        elif request.form.get('save') == 'save':
            form_headers = request.form.get('headers')
            if form_headers:
                form_headers = form_headers.split(',')
            headers_map = {
                tuple(header for header in list(Projects.__mapper__.columns.keys()) + list(Projects.__mapper__.relationships.keys()) if header not in ['tutor_id', 'client_id']): 'projects',
                tuple(header for header in list(Tutors.__mapper__.columns.keys()) + list(Tutors.__mapper__.relationships.keys()) if header not in ['tutor_id', 'client_id']): 'tutors',
                tuple(header for header in list(Clients.__mapper__.columns.keys()) + list(Clients.__mapper__.relationships.keys()) if header not in ['tutor_id', 'client_id']): 'clients'
            }
            table = headers_map.get(tuple(form_headers), None)
            if table:
                table_mapping = {
                    'projects': Projects,
                    'tutors': Tutors,
                    'clients': Clients
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
    return render_template("search.html")
