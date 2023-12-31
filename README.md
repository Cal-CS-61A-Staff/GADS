# GADS - Gradescope Automated Discussion Service <br>
<img src="https://github.com/Cal-CS-61A-Staff/GADS/assets/40013378/a34eb0b4-f8d5-4e78-b3c0-f15c1df36e58" alt="Infra" width="200" height="200">

## Description
This tool automatically pulls discussion attendance from Google Sheets and updates students' discussion assignment. The Google Sheet is the single source of truth. If discussion attendances were removed from Google Sheets, those changes will be reflected in Gradescope.

## Setup
Note: your Gradescope account must be an instructor for the course (not just have a TA or reader role).

1. Create a Gradescope **Homework/Problem Set** assignment <br>
![image](https://github.com/Cal-CS-61A-Staff/GADS/assets/40013378/14bd48b4-315d-4bed-88d6-70b57416213d)

The specific details regarding the assignment don't matter for GADS. Template PDF doesn't matter either, feel free to submit anything. Make sure students upload submissions, not instructors.

2. Each "Question title" should match Google spreadsheet entries. For example, if your Google attendance spreadsheet has values "Disc 1", "Disc 2", "Disc 3", then the question titles should also be "Disc 1", "Disc 2", "Disc 3".

3. The rubric should have 2 items per question. These 2 items should be "Attended" and "Not Attended" (you can modify this by editing the config.json) <br>
![image](https://github.com/Cal-CS-61A-Staff/GADS/assets/40013378/cfe300e8-2241-4299-b1cf-501fad7dc974)

4. In your Google spreadsheet, give the following address "Viewer" permissions: discussion-attendance@cs61a-140900.iam.gserviceaccount.com <br>
![image](https://github.com/Cal-CS-61A-Staff/GADS/assets/40013378/8b7a587a-9a7c-408e-b9ba-6888eace8250)

5. Create a config.json file. Here is an example:
```
{
    "sheet_id": "1aQddcGNf7gKJ43oP8vDXb4ACMM4nv8W9_TH3DkbPDDE",
    "subsheet_name" : "Sheet1",
    "email_column": "A",
    "dis_number_column" : "D",
    "service_account_path" : "xxxxxxxxxx.json",
    "gs_course_id" : "688652",
    "gs_course_name" : "TestCourse",
    "gs_assignment_id" : "3835703",
    "rubric_item_attended_text" : "Attended",
    "rubric_item_not_attended_text" : "Not Attended",
    "num_discussions" : "3"
}
```
![image](https://github.com/Cal-CS-61A-Staff/GADS/assets/40013378/0c36b6c6-d5d8-462c-945d-c3e514289b7d)

![image](https://github.com/Cal-CS-61A-Staff/GADS/assets/40013378/63629bd7-7d80-4810-958a-683959dd61a0)

- sheet_id - the id of your Google sheet <br>

- subsheet_name - name of the subsheet <br>

- email_column - column ID where student emails are located (these emails should be the same as those found in Gradescope)

- dis_number_column - column ID where discussion identifiers are located (should correspond to Gradescope question titles)

- service_account_path - path to json file to service account credentials (default is `discussion-attendance`, but you can use your own service account if you'd like, just make sure it has permissions to your Google sheet)

- gs_course_id - ID of the Gradescope course

- gs_assignment_id - ID of the Gradescope assignment

- rubric_item_attended_text - rubric item names corresponding to attendance

- rubric_item_not_attended_text - rubric item names corresponding to not attendance

- num_discussions - total number of discussions in the course

  6. Run `python update_attendance.py -u <your gradescope username>`. You will be prompted to enter your password. Do that.
 
  Note: for large courses, this script can take up to 30 min to run. If you would like your script to run automatically on 61a's GCP, contact 61a infra. 
