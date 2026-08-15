import requests
import json

base_url = 'http://localhost:8000/api/v1'
# 1. Login
login_data = {'email': 'student@example.com', 'password': 'student123'}
r = requests.post(f'{base_url}/auth/login', json=login_data)
if r.status_code != 200:
    print('Login failed:', r.text)
    exit(1)
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Upload and Submit (Step 2)
file_path = r'D:\TTTN\personalized-learning-system\personalized-learning-system\test\Test_exam.jpg'

questionsPayload = [
    {
        'id': 'Câu I',
        'content': 'Cho hai biểu thức',
        'level': 'Không biết làm'
    }
]

data = {
    'mode': 'post_exam',
    'selected_questions': json.dumps(questionsPayload),
    'raw_text': 'raw text content',
    'exam_score': '5',
    'exam_max_score': '10'
}

with open(file_path, 'rb') as f:
    files = {'file': f}
    r2 = requests.post(f'{base_url}/learners/me/exams', headers=headers, data=data, files=files)
    print('Status:', r2.status_code)
    print('Response:', r2.text)
