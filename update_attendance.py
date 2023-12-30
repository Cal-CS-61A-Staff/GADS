import argparse
import json
from gs_api.pyscope.pyscope import GSConnection
import getpass

from googleapiclient.discovery import build
from google.oauth2 import service_account

from bs4 import BeautifulSoup
from collections import defaultdict

from time import perf_counter

# Create ArgumentParser object
parser = argparse.ArgumentParser(description='Script to handle command line arguments')

# Add arguments with specific tags
parser.add_argument('-u', '--user', help='Gradescope username', required=True)

# Parse the arguments
args = parser.parse_args()

user = args.user
password = getpass.getpass()


# Read config file
with open('config.json', 'r') as f:
    config = json.load(f)

# Obtain attendance information from sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SERVICE_ACCOUNT_FILE = config['service_account_path']
SPREADSHEET_ID = config['sheet_id']

email_spreadsheet_range = f"{config['subsheet_name']}!{config['email_column']}1:{config['email_column']}999999"
dis_spreadsheet_range = f"{config['subsheet_name']}!{config['dis_number_column']}1:{config['dis_number_column']}999999"


creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials = creds)

sheet = service.spreadsheets()

email_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=email_spreadsheet_range).execute()
email_values = email_result.get('values', [])

dis_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=dis_spreadsheet_range).execute()
dis_values = dis_result.get('values', [])

emails = sum(email_values, start=[])
dis = sum(dis_values, start=[])

emails = list(map(lambda x: x.replace(" ", ""), emails))

assert len(emails) == len(dis), f"Length of emails column (column {config['email_column']}) is {len(emails)} while length of dis_number column (column {config['dis_number_column']}) is {len(dis)}"

# keys - emails, values - list of strings of discussion numbers
attendances_dict = defaultdict(list)

for email, dis_num in zip(emails, dis):
    attendances_dict[email].append(dis_num)

# Connect to gradescope
gs_session = GSConnection()

if not gs_session.login(user, password):
    raise Exception("Username or password is incorrect")

start = perf_counter()
for i in range(1000):
    a = perf_counter()

    # Grab assignment submissions HTML
    html_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    submissions_resp = gs_session.session.get(f"https://www.gradescope.com/courses/{config['gs_course_id']}/assignments/{config['gs_assignment_id']}/submissions", headers=html_headers)

    if submissions_resp.status_code == 401:
        raise Exception(f"Forbidden, you are not an instructor of the course with ID {config['gs_course_id']}")
    elif submissions_resp.status_code != 200:
        raise Exception(f"Exception: {submissions_resp.text}")

    submissions_dict = json.loads(submissions_resp.text)['submissions']
    # Keys - string member id, values - string submission id
    submissions_dict = {str(val['active_user_ids'][0]) : key for key, val in submissions_dict.items()}

    # Get mappings from emails to member IDs
    memberships_resp = gs_session.session.get(f"https://www.gradescope.com/courses/{config['gs_course_id']}/memberships")
    if memberships_resp.status_code != 200:
        raise Exception(f"Exception: {submissions_resp.text}")


    soup = BeautifulSoup(memberships_resp.text, 'html.parser')

    # Find all buttons with class 'js-rosterName'

    # keys - email, values - membership ID (string)
    memberships_dict = {}
    roster_buttons = soup.find_all('button', class_='js-rosterName')
    if roster_buttons:
        for button in roster_buttons:
            email = button.find_next('td').text.strip()
            user_id = button.get('data-url').split('=')[-1]

            memberships_dict[email] = user_id
    else:
        raise Exception(f"Buttons with tag 'js-rosterName' not found in endpoint https://www.gradescope.com/courses/{config['gs_course_id']}/memberships when searching for email-ID mapping")

    # Use the first submission ID in order to get all question IDs
    question_resp = gs_session.session.get(f"https://www.gradescope.com/courses/{config['gs_course_id']}/assignments/{config['gs_assignment_id']}/grade")
    if question_resp.status_code != 200:
        raise Exception(f"Attempting to identify question IDs. Received status code {question_resp.status_code} and message {question_resp.text}.")

    soup = BeautifulSoup(question_resp.text, 'html.parser')

    # Find the div containing data-react-props
    div = soup.find('div', {'data-react-class': 'GradingDashboard'})

    # Extract the data-react-props attribute value
    data_props = div['data-react-props']

    # Load the JSON data
    json_data = json.loads(data_props)

    questions = json_data['presenter']['assignments'][config['gs_assignment_id']]['questions']

    # Keys - strings of question name, values - strings of question id
    questions_dict = {}
    for question_id, question_data in questions.items():
        question_name = question_data['title']
        question_id = question_data['id']

        questions_dict[question_name] = question_id

    def assign_grade(email, attendance, qid_grade_id_mapping, qid_attended_rid_mapping, qid_not_attended_rid_mapping, attended):
        curr_question_id = questions_dict[attendance]
        grade_id = qid_grade_id_mapping[curr_question_id]
        attended_rubric_id = qid_attended_rid_mapping[curr_question_id]
        not_attended_rubric_id = qid_not_attended_rid_mapping[curr_question_id]

        # Acquire CSRF token
        get_resp = gs_session.session.get(f"https://www.gradescope.com/courses/{config['gs_course_id']}/questions/{curr_question_id}/submissions/{grade_id}/grade")
        parsed_outline_resp = BeautifulSoup(get_resp.text, 'html.parser')
        if not get_resp.ok:
            raise Exception(f"Failed to acquire csrf token for student {email}. {get_resp.text}")
        authenticity_token = parsed_outline_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        post_header = {'X-Csrf-token' : authenticity_token}

        if attended:
            attended_score = "true"
            not_attended_score = "false"
        else:
            attended_score = "false"
            not_attended_score = "true"

        payload = {"rubric_items" : {str(attended_rubric_id) : {"score" : attended_score}, str(not_attended_rubric_id) : {"score" : not_attended_score}}, "question_submission_evaluation": {"points": None, "comments": None}}
        post_resp = gs_session.session.post(f"https://www.gradescope.com/courses/{config['gs_course_id']}/questions/{curr_question_id}/submissions/{grade_id}/save_grade", json = payload, headers=post_header)
        
        if not post_resp.ok:
            raise Exception(f"Failed to update grades for {email}")

    # For each person in the attendances list, get their submission ID and corresponding attendances list
    for email, attendance_list in attendances_dict.items():
        if email in memberships_dict and memberships_dict[email] in submissions_dict:
            curr_submission_id = submissions_dict[memberships_dict[email]]

            # Keys - string of question id, Values - string of rubric id corresponding to attended
            qid_attended_rid_mapping = {}

            # Keys - string of question id, Values - string of grade path id
            qid_grade_id_mapping = {}

            # Get question ID to rubric item mapping
            # We have the question id, get the corresponding grade_path id
            grade_path_resp_headers = {"Accept" : "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7", "User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"}
            grade_path_resp = gs_session.session.get(f"https://www.gradescope.com/courses/{config['gs_course_id']}/assignments/{config['gs_assignment_id']}/submissions/{curr_submission_id}", headers=grade_path_resp_headers)

            if grade_path_resp.status_code != 200:
                raise Exception(f"Attempting to identify grade paths. Received status code {grade_path_resp.status_code} and message {grade_path_resp.text}.")

            soup = BeautifulSoup(grade_path_resp.text, 'html.parser')

            # Find the div containing the data-react-props
            data_div = soup.find('div', {'data-react-class': 'AssignmentSubmissionViewer'})

            if data_div:
                # Get the data-react-props attribute
                data_props = data_div.get('data-react-props')
                
                # Convert the data-react-props string to a dictionary
                data_props = json.loads(data_props.replace('&quot;', '"'))  # Safely convert string to dictionary

                # Extract question IDs and corresponding IDs
                inorder_leaf_question_ids = data_props.get('question_submissions', [])
                outline = data_props.get('questions', [])

                qid_grade_id_mapping = {item['question_id'] : item['id'] for item in data_props['question_submissions']}
                qid_attended_rid_mapping = {item['question_id'] : item['id'] for item in data_props['rubric_items'] if item['description'] == config['rubric_item_attended_text']}
                qid_not_attended_rid_mapping = {item['question_id'] : item['id'] for item in data_props['rubric_items'] if item['description'] == config['rubric_item_not_attended_text']}
                
                assert len(qid_grade_id_mapping) == int(config['num_discussions']), f"Number of grade id paths ({len(qid_grade_id_mapping)}) doesn't align with total number of discussions ({config['num_discussions']}) in config."
                assert len(qid_attended_rid_mapping) == int(config['num_discussions']), f"Number of rubric ids ({len(qid_attended_rid_mapping)}) doesn't align with total number of discussions in config ({config['num_discussions']}). Check if rubric_item_attended_text matches the Gradescope rubric's description"
                assert len(qid_not_attended_rid_mapping) == int(config['num_discussions']), f"Number of rubric ids ({len(qid_not_attended_rid_mapping)}) doesn't align with total number of discussions in config ({config['num_discussions']}). Check if rubric_item_not_attended_text matches the Gradescope rubric's description"
            else:
                raise Exception("Could not find AssignmentSubmissionViewer react class")

            # Grade everything in attendance_list as attend, everything outside of attendance_list as not attended
            
            not_attended_set = set(questions_dict.keys()) - set(attendance_list) # set of all discussions not attended by this student

            # Iterate through all questions and update scores
            for attendance in attendance_list:
                if not attendance in questions_dict:
                    raise Exception(f"{email} submitted {attendance} which was not found as a Gradescope question. Google form responses must correspond to Gradescope question names for assignment {config['gs_assignment_id']}")
                assign_grade(email, attendance, qid_grade_id_mapping, qid_attended_rid_mapping, qid_not_attended_rid_mapping, attended = True)

            for attendance in not_attended_set:
                if not attendance in questions_dict:
                    raise Exception(f"{email} submitted {attendance} which was not found as a Gradescope question. Google form responses must correspond to Gradescope question names for assignment {config['gs_assignment_id']}")
                assign_grade(email, attendance, qid_grade_id_mapping, qid_attended_rid_mapping, qid_not_attended_rid_mapping, attended = False)
            
            print(f"Finished updated grades for {email}")
        else:
            print(f"WARNING: {email} is either not enrolled in Gradescope or has not submitted into assignment {config['gs_assignment_id']}")
        
        
    print(f"Loop {i} finished. Time: {perf_counter() - a}")
print(f"Total time: {perf_counter() - start}")