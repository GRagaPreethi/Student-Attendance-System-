from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date, timedelta
import jwt
from passlib.context import CryptContext
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Student Attendance System")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# JWT Configuration
JWT_SECRET = "your-secret-key-here"  # In production, use a secure secret
JWT_ALGORITHM = "HS256"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password_hash: str
    role: str  # "admin" or "teacher"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: datetime

class Class(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    subject: str
    teacher_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ClassCreate(BaseModel):
    name: str
    subject: str
    teacher_id: str

class Student(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    class_id: str
    roll_number: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class StudentCreate(BaseModel):
    name: str
    email: str
    class_id: str
    roll_number: str

class Attendance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    class_id: str
    student_id: str
    date: date
    status: str  # "present", "absent", "late"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AttendanceCreate(BaseModel):
    class_id: str
    student_id: str
    date: date
    status: str

class AttendanceBulkCreate(BaseModel):
    class_id: str
    date: date
    attendance_records: List[dict]  # [{"student_id": "xxx", "status": "present"}]

# Helper Functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_jwt_token(data: dict) -> str:
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_jwt_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return UserResponse(**user)

# Authentication Routes
@api_router.post("/auth/register", response_model=dict)
async def register_user(user_data: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password and create user
    hashed_password = hash_password(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role
    )
    
    await db.users.insert_one(user.dict())
    
    # Create JWT token
    token = create_jwt_token({"user_id": user.id})
    
    return {
        "message": "User registered successfully",
        "token": token,
        "user": UserResponse(**user.dict())
    }

@api_router.post("/auth/login", response_model=dict)
async def login_user(login_data: UserLogin):
    # Find user by email
    user = await db.users.find_one({"email": login_data.email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    # Verify password
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    # Create JWT token
    token = create_jwt_token({"user_id": user["id"]})
    
    return {
        "message": "Login successful",
        "token": token,
        "user": UserResponse(**user)
    }

# Classes Routes
@api_router.get("/classes", response_model=List[Class])
async def get_classes(current_user: UserResponse = Depends(get_current_user)):
    if current_user.role == "teacher":
        classes = await db.classes.find({"teacher_id": current_user.id}).to_list(1000)
    else:  # admin
        classes = await db.classes.find().to_list(1000)
    return [Class(**class_doc) for class_doc in classes]

@api_router.post("/classes", response_model=Class)
async def create_class(class_data: ClassCreate, current_user: UserResponse = Depends(get_current_user)):
    if current_user.role != "admin" and class_data.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to create class for another teacher")
    
    new_class = Class(**class_data.dict())
    await db.classes.insert_one(new_class.dict())
    return new_class

@api_router.put("/classes/{class_id}", response_model=Class)
async def update_class(class_id: str, class_data: ClassCreate, current_user: UserResponse = Depends(get_current_user)):
    existing_class = await db.classes.find_one({"id": class_id})
    if not existing_class:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and existing_class["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this class")
    
    updated_class = Class(**class_data.dict())
    updated_class.id = class_id
    await db.classes.update_one({"id": class_id}, {"$set": updated_class.dict()})
    return updated_class

@api_router.delete("/classes/{class_id}")
async def delete_class(class_id: str, current_user: UserResponse = Depends(get_current_user)):
    existing_class = await db.classes.find_one({"id": class_id})
    if not existing_class:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and existing_class["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this class")
    
    await db.classes.delete_one({"id": class_id})
    return {"message": "Class deleted successfully"}

# Students Routes
@api_router.get("/students", response_model=List[Student])
async def get_students(class_id: Optional[str] = None, current_user: UserResponse = Depends(get_current_user)):
    query = {}
    if class_id:
        query["class_id"] = class_id
    
    students = await db.students.find(query).to_list(1000)
    return [Student(**student) for student in students]

@api_router.post("/students", response_model=Student)
async def create_student(student_data: StudentCreate, current_user: UserResponse = Depends(get_current_user)):
    # Check if class exists and user has permission
    class_doc = await db.classes.find_one({"id": student_data.class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and class_doc["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to add student to this class")
    
    new_student = Student(**student_data.dict())
    await db.students.insert_one(new_student.dict())
    return new_student

@api_router.put("/students/{student_id}", response_model=Student)
async def update_student(student_id: str, student_data: StudentCreate, current_user: UserResponse = Depends(get_current_user)):
    existing_student = await db.students.find_one({"id": student_id})
    if not existing_student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check permissions
    class_doc = await db.classes.find_one({"id": student_data.class_id})
    if current_user.role != "admin" and class_doc["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this student")
    
    updated_student = Student(**student_data.dict())
    updated_student.id = student_id
    await db.students.update_one({"id": student_id}, {"$set": updated_student.dict()})
    return updated_student

@api_router.delete("/students/{student_id}")
async def delete_student(student_id: str, current_user: UserResponse = Depends(get_current_user)):
    existing_student = await db.students.find_one({"id": student_id})
    if not existing_student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check permissions
    class_doc = await db.classes.find_one({"id": existing_student["class_id"]})
    if current_user.role != "admin" and class_doc["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this student")
    
    await db.students.delete_one({"id": student_id})
    return {"message": "Student deleted successfully"}

# Attendance Routes
@api_router.post("/attendance/bulk", response_model=dict)
async def mark_bulk_attendance(attendance_data: AttendanceBulkCreate, current_user: UserResponse = Depends(get_current_user)):
    # Check if class exists and user has permission
    class_doc = await db.classes.find_one({"id": attendance_data.class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and class_doc["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to mark attendance for this class")
    
    # Delete existing attendance for this class and date
    await db.attendance.delete_many({
        "class_id": attendance_data.class_id,
        "date": attendance_data.date
    })
    
    # Insert new attendance records
    attendance_records = []
    for record in attendance_data.attendance_records:
        attendance = Attendance(
            class_id=attendance_data.class_id,
            student_id=record["student_id"],
            date=attendance_data.date,
            status=record["status"]
        )
        attendance_records.append(attendance.dict())
    
    if attendance_records:
        await db.attendance.insert_many(attendance_records)
    
    return {"message": f"Attendance marked for {len(attendance_records)} students"}

@api_router.get("/attendance", response_model=List[dict])
async def get_attendance(class_id: str, date: date, current_user: UserResponse = Depends(get_current_user)):
    # Check permissions
    class_doc = await db.classes.find_one({"id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and class_doc["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view attendance for this class")
    
    # Get students in class
    students = await db.students.find({"class_id": class_id}).to_list(1000)
    
    # Get attendance records
    attendance_records = await db.attendance.find({
        "class_id": class_id,
        "date": date
    }).to_list(1000)
    
    # Combine data
    attendance_map = {record["student_id"]: record["status"] for record in attendance_records}
    
    result = []
    for student in students:
        result.append({
            "student_id": student["id"],
            "student_name": student["name"],
            "roll_number": student["roll_number"],
            "status": attendance_map.get(student["id"], "not_marked")
        })
    
    return result

@api_router.get("/attendance/report/csv")
async def download_attendance_csv(class_id: str, start_date: date, end_date: date, current_user: UserResponse = Depends(get_current_user)):
    # Check permissions
    class_doc = await db.classes.find_one({"id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if current_user.role != "admin" and class_doc["teacher_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to generate report for this class")
    
    # Get students and attendance data
    students = await db.students.find({"class_id": class_id}).to_list(1000)
    attendance_records = await db.attendance.find({
        "class_id": class_id,
        "date": {"$gte": start_date, "$lte": end_date}
    }).to_list(1000)
    
    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    
    header = ["Student Name", "Roll Number"] + date_range
    writer.writerow(header)
    
    # Data rows
    attendance_map = {}
    for record in attendance_records:
        key = f"{record['student_id']}_{record['date']}"
        attendance_map[key] = record['status']
    
    for student in students:
        row = [student["name"], student["roll_number"]]
        for date_str in date_range:
            key = f"{student['id']}_{date_str}"
            status = attendance_map.get(key, "not_marked")
            row.append(status)
        writer.writerow(row)
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_report_{class_id}_{start_date}_{end_date}.csv"}
    )

# Users management (Admin only)
@api_router.get("/users", response_model=List[UserResponse])
async def get_users(current_user: UserResponse = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view users")
    
    users = await db.users.find().to_list(1000)
    return [UserResponse(**user) for user in users]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()