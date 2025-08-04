#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Student Attendance System
Tests all endpoints with realistic data and scenarios
"""

import requests
import json
from datetime import datetime, date, timedelta
import sys
import os

# Backend URL from frontend .env
BACKEND_URL = "https://07d2f872-51c5-4589-bf4c-7baec1835023.preview.emergentagent.com/api"

class AttendanceSystemTester:
    def __init__(self):
        self.admin_token = None
        self.teacher_token = None
        self.admin_user = None
        self.teacher_user = None
        self.test_class_id = None
        self.test_students = []
        self.results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }

    def log_result(self, test_name, success, message=""):
        if success:
            print(f"✅ {test_name}: PASSED")
            self.results["passed"] += 1
        else:
            print(f"❌ {test_name}: FAILED - {message}")
            self.results["failed"] += 1
            self.results["errors"].append(f"{test_name}: {message}")

    def test_user_registration(self):
        """Test user registration for both admin and teacher roles"""
        print("\n=== Testing User Registration ===")
        
        # Test admin registration
        admin_data = {
            "username": "Sarah Johnson",
            "email": "sarah.johnson@school.edu",
            "password": "SecurePass123!",
            "role": "admin"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/auth/register", json=admin_data)
            if response.status_code == 200:
                data = response.json()
                self.admin_token = data.get("token")
                self.admin_user = data.get("user")
                self.log_result("Admin Registration", True)
            else:
                self.log_result("Admin Registration", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Admin Registration", False, f"Exception: {str(e)}")

        # Test teacher registration
        teacher_data = {
            "username": "Michael Chen",
            "email": "michael.chen@school.edu", 
            "password": "TeacherPass456!",
            "role": "teacher"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/auth/register", json=teacher_data)
            if response.status_code == 200:
                data = response.json()
                self.teacher_token = data.get("token")
                self.teacher_user = data.get("user")
                self.log_result("Teacher Registration", True)
            else:
                self.log_result("Teacher Registration", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Teacher Registration", False, f"Exception: {str(e)}")

        # Test duplicate email registration
        try:
            response = requests.post(f"{BACKEND_URL}/auth/register", json=admin_data)
            if response.status_code == 400:
                self.log_result("Duplicate Email Prevention", True)
            else:
                self.log_result("Duplicate Email Prevention", False, f"Expected 400, got {response.status_code}")
        except Exception as e:
            self.log_result("Duplicate Email Prevention", False, f"Exception: {str(e)}")

    def test_user_login(self):
        """Test user login with valid credentials"""
        print("\n=== Testing User Login ===")
        
        # Test admin login
        admin_login = {
            "email": "sarah.johnson@school.edu",
            "password": "SecurePass123!"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/auth/login", json=admin_login)
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                if token:
                    self.log_result("Admin Login", True)
                else:
                    self.log_result("Admin Login", False, "No token in response")
            else:
                self.log_result("Admin Login", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Admin Login", False, f"Exception: {str(e)}")

        # Test teacher login
        teacher_login = {
            "email": "michael.chen@school.edu",
            "password": "TeacherPass456!"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/auth/login", json=teacher_login)
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                if token:
                    self.log_result("Teacher Login", True)
                else:
                    self.log_result("Teacher Login", False, "No token in response")
            else:
                self.log_result("Teacher Login", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Teacher Login", False, f"Exception: {str(e)}")

        # Test invalid credentials
        invalid_login = {
            "email": "sarah.johnson@school.edu",
            "password": "WrongPassword"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/auth/login", json=invalid_login)
            if response.status_code == 400:
                self.log_result("Invalid Credentials Rejection", True)
            else:
                self.log_result("Invalid Credentials Rejection", False, f"Expected 400, got {response.status_code}")
        except Exception as e:
            self.log_result("Invalid Credentials Rejection", False, f"Exception: {str(e)}")

    def test_jwt_token_validation(self):
        """Test JWT token validation on protected endpoints"""
        print("\n=== Testing JWT Token Validation ===")
        
        # Test with valid token
        if self.admin_token:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            try:
                response = requests.get(f"{BACKEND_URL}/classes", headers=headers)
                if response.status_code in [200, 404]:  # 404 is ok if no classes exist yet
                    self.log_result("Valid Token Access", True)
                else:
                    self.log_result("Valid Token Access", False, f"Status: {response.status_code}")
            except Exception as e:
                self.log_result("Valid Token Access", False, f"Exception: {str(e)}")

        # Test without token
        try:
            response = requests.get(f"{BACKEND_URL}/classes")
            if response.status_code == 403:  # FastAPI HTTPBearer returns 403
                self.log_result("No Token Rejection", True)
            else:
                self.log_result("No Token Rejection", False, f"Expected 403, got {response.status_code}")
        except Exception as e:
            self.log_result("No Token Rejection", False, f"Exception: {str(e)}")

        # Test with invalid token
        headers = {"Authorization": "Bearer invalid_token_here"}
        try:
            response = requests.get(f"{BACKEND_URL}/classes", headers=headers)
            if response.status_code == 401:
                self.log_result("Invalid Token Rejection", True)
            else:
                self.log_result("Invalid Token Rejection", False, f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.log_result("Invalid Token Rejection", False, f"Exception: {str(e)}")

    def test_classes_crud(self):
        """Test Classes CRUD operations with role-based permissions"""
        print("\n=== Testing Classes CRUD API ===")
        
        if not self.admin_token or not self.teacher_token:
            self.log_result("Classes CRUD Setup", False, "Missing authentication tokens")
            return

        # Test admin creating class
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        class_data = {
            "name": "Advanced Mathematics",
            "subject": "Mathematics",
            "teacher_id": self.teacher_user["id"]
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/classes", json=class_data, headers=admin_headers)
            if response.status_code == 200:
                data = response.json()
                self.test_class_id = data.get("id")
                self.log_result("Admin Create Class", True)
            else:
                self.log_result("Admin Create Class", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Admin Create Class", False, f"Exception: {str(e)}")

        # Test teacher creating class for themselves
        teacher_headers = {"Authorization": f"Bearer {self.teacher_token}"}
        teacher_class_data = {
            "name": "Physics Lab",
            "subject": "Physics",
            "teacher_id": self.teacher_user["id"]
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/classes", json=teacher_class_data, headers=teacher_headers)
            if response.status_code == 200:
                self.log_result("Teacher Create Own Class", True)
            else:
                self.log_result("Teacher Create Own Class", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Teacher Create Own Class", False, f"Exception: {str(e)}")

        # Test teacher trying to create class for another teacher (should fail)
        unauthorized_class_data = {
            "name": "Unauthorized Class",
            "subject": "Chemistry",
            "teacher_id": self.admin_user["id"]  # Different teacher
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/classes", json=unauthorized_class_data, headers=teacher_headers)
            if response.status_code == 403:
                self.log_result("Teacher Unauthorized Class Creation", True)
            else:
                self.log_result("Teacher Unauthorized Class Creation", False, f"Expected 403, got {response.status_code}")
        except Exception as e:
            self.log_result("Teacher Unauthorized Class Creation", False, f"Exception: {str(e)}")

        # Test getting classes (role-based filtering)
        try:
            response = requests.get(f"{BACKEND_URL}/classes", headers=admin_headers)
            if response.status_code == 200:
                admin_classes = response.json()
                self.log_result("Admin Get All Classes", True)
            else:
                self.log_result("Admin Get All Classes", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Admin Get All Classes", False, f"Exception: {str(e)}")

        try:
            response = requests.get(f"{BACKEND_URL}/classes", headers=teacher_headers)
            if response.status_code == 200:
                teacher_classes = response.json()
                self.log_result("Teacher Get Own Classes", True)
            else:
                self.log_result("Teacher Get Own Classes", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Teacher Get Own Classes", False, f"Exception: {str(e)}")

        # Test updating class
        if self.test_class_id:
            update_data = {
                "name": "Advanced Mathematics - Updated",
                "subject": "Mathematics",
                "teacher_id": self.teacher_user["id"]
            }
            
            try:
                response = requests.put(f"{BACKEND_URL}/classes/{self.test_class_id}", json=update_data, headers=admin_headers)
                if response.status_code == 200:
                    self.log_result("Update Class", True)
                else:
                    self.log_result("Update Class", False, f"Status: {response.status_code}, Response: {response.text}")
            except Exception as e:
                self.log_result("Update Class", False, f"Exception: {str(e)}")

    def test_students_crud(self):
        """Test Students CRUD operations with permission checks"""
        print("\n=== Testing Students CRUD API ===")
        
        if not self.test_class_id:
            self.log_result("Students CRUD Setup", False, "No test class available")
            return

        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        teacher_headers = {"Authorization": f"Bearer {self.teacher_token}"}

        # Test creating students
        students_data = [
            {
                "name": "Emma Rodriguez",
                "email": "emma.rodriguez@student.edu",
                "class_id": self.test_class_id,
                "roll_number": "MATH001"
            },
            {
                "name": "James Wilson",
                "email": "james.wilson@student.edu", 
                "class_id": self.test_class_id,
                "roll_number": "MATH002"
            },
            {
                "name": "Aisha Patel",
                "email": "aisha.patel@student.edu",
                "class_id": self.test_class_id,
                "roll_number": "MATH003"
            }
        ]

        for i, student_data in enumerate(students_data):
            try:
                response = requests.post(f"{BACKEND_URL}/students", json=student_data, headers=admin_headers)
                if response.status_code == 200:
                    student = response.json()
                    self.test_students.append(student)
                    self.log_result(f"Create Student {i+1}", True)
                else:
                    self.log_result(f"Create Student {i+1}", False, f"Status: {response.status_code}, Response: {response.text}")
            except Exception as e:
                self.log_result(f"Create Student {i+1}", False, f"Exception: {str(e)}")

        # Test getting students by class
        try:
            response = requests.get(f"{BACKEND_URL}/students?class_id={self.test_class_id}", headers=teacher_headers)
            if response.status_code == 200:
                students = response.json()
                self.log_result("Get Students by Class", True)
            else:
                self.log_result("Get Students by Class", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Get Students by Class", False, f"Exception: {str(e)}")

        # Test getting all students (admin)
        try:
            response = requests.get(f"{BACKEND_URL}/students", headers=admin_headers)
            if response.status_code == 200:
                all_students = response.json()
                self.log_result("Admin Get All Students", True)
            else:
                self.log_result("Admin Get All Students", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Admin Get All Students", False, f"Exception: {str(e)}")

        # Test updating student
        if self.test_students:
            student_id = self.test_students[0]["id"]
            update_data = {
                "name": "Emma Rodriguez-Smith",
                "email": "emma.rodriguez@student.edu",
                "class_id": self.test_class_id,
                "roll_number": "MATH001"
            }
            
            try:
                response = requests.put(f"{BACKEND_URL}/students/{student_id}", json=update_data, headers=teacher_headers)
                if response.status_code == 200:
                    self.log_result("Update Student", True)
                else:
                    self.log_result("Update Student", False, f"Status: {response.status_code}, Response: {response.text}")
            except Exception as e:
                self.log_result("Update Student", False, f"Exception: {str(e)}")

    def test_attendance_tracking(self):
        """Test Attendance tracking API - bulk marking and retrieval"""
        print("\n=== Testing Attendance Tracking API ===")
        
        if not self.test_class_id or not self.test_students:
            self.log_result("Attendance Setup", False, "Missing test class or students")
            return

        teacher_headers = {"Authorization": f"Bearer {self.teacher_token}"}
        today = date.today()

        # Test bulk attendance marking
        attendance_data = {
            "class_id": self.test_class_id,
            "date": today.isoformat(),
            "attendance_records": [
                {"student_id": self.test_students[0]["id"], "status": "present"},
                {"student_id": self.test_students[1]["id"], "status": "absent"},
                {"student_id": self.test_students[2]["id"], "status": "late"}
            ]
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/attendance/bulk", json=attendance_data, headers=teacher_headers)
            if response.status_code == 200:
                self.log_result("Bulk Attendance Marking", True)
            else:
                self.log_result("Bulk Attendance Marking", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("Bulk Attendance Marking", False, f"Exception: {str(e)}")

        # Test retrieving attendance records
        try:
            response = requests.get(f"{BACKEND_URL}/attendance?class_id={self.test_class_id}&date={today.isoformat()}", headers=teacher_headers)
            if response.status_code == 200:
                attendance_records = response.json()
                if len(attendance_records) == len(self.test_students):
                    self.log_result("Retrieve Attendance Records", True)
                else:
                    self.log_result("Retrieve Attendance Records", False, f"Expected {len(self.test_students)} records, got {len(attendance_records)}")
            else:
                self.log_result("Retrieve Attendance Records", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Retrieve Attendance Records", False, f"Exception: {str(e)}")

        # Test attendance for different date
        yesterday = today - timedelta(days=1)
        yesterday_attendance = {
            "class_id": self.test_class_id,
            "date": yesterday.isoformat(),
            "attendance_records": [
                {"student_id": self.test_students[0]["id"], "status": "present"},
                {"student_id": self.test_students[1]["id"], "status": "present"},
                {"student_id": self.test_students[2]["id"], "status": "absent"}
            ]
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/attendance/bulk", json=yesterday_attendance, headers=teacher_headers)
            if response.status_code == 200:
                self.log_result("Different Date Attendance", True)
            else:
                self.log_result("Different Date Attendance", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Different Date Attendance", False, f"Exception: {str(e)}")

    def test_csv_reports(self):
        """Test CSV report generation with date ranges"""
        print("\n=== Testing CSV Report Generation ===")
        
        if not self.test_class_id:
            self.log_result("CSV Report Setup", False, "No test class available")
            return

        teacher_headers = {"Authorization": f"Bearer {self.teacher_token}"}
        today = date.today()
        start_date = today - timedelta(days=7)
        end_date = today

        # Test CSV report generation
        try:
            response = requests.get(
                f"{BACKEND_URL}/attendance/report/csv?class_id={self.test_class_id}&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}",
                headers=teacher_headers
            )
            if response.status_code == 200:
                # Check if response is CSV format
                content_type = response.headers.get('content-type', '')
                if 'text/csv' in content_type:
                    self.log_result("CSV Report Generation", True)
                else:
                    self.log_result("CSV Report Generation", False, f"Expected CSV content-type, got {content_type}")
            else:
                self.log_result("CSV Report Generation", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_result("CSV Report Generation", False, f"Exception: {str(e)}")

        # Test CSV report with admin permissions
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        try:
            response = requests.get(
                f"{BACKEND_URL}/attendance/report/csv?class_id={self.test_class_id}&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}",
                headers=admin_headers
            )
            if response.status_code == 200:
                self.log_result("Admin CSV Report Access", True)
            else:
                self.log_result("Admin CSV Report Access", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Admin CSV Report Access", False, f"Exception: {str(e)}")

    def test_role_based_permissions(self):
        """Test role-based permission enforcement"""
        print("\n=== Testing Role-Based Permissions ===")
        
        if not self.admin_token or not self.teacher_token:
            self.log_result("Permission Test Setup", False, "Missing authentication tokens")
            return

        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        teacher_headers = {"Authorization": f"Bearer {self.teacher_token}"}

        # Test admin-only endpoint (get all users)
        try:
            response = requests.get(f"{BACKEND_URL}/users", headers=admin_headers)
            if response.status_code == 200:
                self.log_result("Admin Access Users Endpoint", True)
            else:
                self.log_result("Admin Access Users Endpoint", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Admin Access Users Endpoint", False, f"Exception: {str(e)}")

        # Test teacher trying to access admin-only endpoint
        try:
            response = requests.get(f"{BACKEND_URL}/users", headers=teacher_headers)
            if response.status_code == 403:
                self.log_result("Teacher Blocked from Users Endpoint", True)
            else:
                self.log_result("Teacher Blocked from Users Endpoint", False, f"Expected 403, got {response.status_code}")
        except Exception as e:
            self.log_result("Teacher Blocked from Users Endpoint", False, f"Exception: {str(e)}")

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Comprehensive Backend API Testing")
        print(f"Backend URL: {BACKEND_URL}")
        print("=" * 60)
        
        self.test_user_registration()
        self.test_user_login()
        self.test_jwt_token_validation()
        self.test_classes_crud()
        self.test_students_crud()
        self.test_attendance_tracking()
        self.test_csv_reports()
        self.test_role_based_permissions()
        
        print("\n" + "=" * 60)
        print("🏁 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📊 Total: {self.results['passed'] + self.results['failed']}")
        
        if self.results['errors']:
            print("\n🔍 FAILED TESTS:")
            for error in self.results['errors']:
                print(f"  • {error}")
        
        success_rate = (self.results['passed'] / (self.results['passed'] + self.results['failed'])) * 100 if (self.results['passed'] + self.results['failed']) > 0 else 0
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        
        return self.results['failed'] == 0

if __name__ == "__main__":
    tester = AttendanceSystemTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)