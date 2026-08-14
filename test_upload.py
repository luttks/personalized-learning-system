import requests

base_url = 'http://localhost:8000/api/v1'
# 1. Login
login_data = {'email': 'student@example.com', 'password': 'student123'}
r = requests.post(f'{base_url}/auth/login', json=login_data)
if r.status_code != 200:
    print('Login failed:', r.text)
    exit(1)
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Upload file
file_path = r'D:\TTTN\personalized-learning-system\personalized-learning-system\test\Test_exam.jpg'
with open(file_path, 'rb') as f:
    files = {'file': f}
    r2 = requests.post(f'{base_url}/learners/me/exams/parse-exam', headers=headers, files=files)
    print('Status:', r2.status_code)
    print('Response:', r2.text)
