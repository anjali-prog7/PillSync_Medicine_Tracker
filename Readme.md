#  PillSync – Intelligent Medicine Reminder and Medication Tracking Platform

##  Project Overview

PillSync is an AI-powered Medicine Reminder and Medication Tracking Platform designed to help patients take medicines on time, improve medication adherence, and allow caregivers to monitor medication schedules.

This repository currently contains the **Milestone 1 (Backend Foundation)** implementation using Django, Django REST Framework, PostgreSQL, and JWT Authentication.

---

#  Milestone 1 Objectives

- Backend project setup using Django
- PostgreSQL database integration
- Custom User Authentication
- JWT-based authentication
- Medicine Management Model
- Reminder Management Model
- Django Admin Configuration
- API Testing using Postman

---

#  Tech Stack

| Technology | Purpose |
|------------|---------|
| Python | Programming Language |
| Django | Backend Framework |
| Django REST Framework | REST API Development |
| PostgreSQL | Relational Database |
| JWT (Simple JWT) | Secure Authentication |
| Postman | API Testing |
| Django Admin | Database Management |

---

#  Project Structure

```
backend/
│
├── accounts/
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   └── views.py
│
├── medicines/
│   ├── models.py
│
├── reminders/
│   ├── models.py
│
├── config/
│   ├── settings.py
│   └── urls.py
│
├── manage.py
├── requirements.txt
└── .env
```

---

#  Features Completed

## 1. Django Backend Setup

- Django project created
- Virtual Environment configured
- Required dependencies installed
- Django REST Framework configured

---

## 2. PostgreSQL Integration

- PostgreSQL installed
- Database created
- Django connected with PostgreSQL
- Environment variables configured using `.env`

Database Configuration:

```
ENGINE = django.db.backends.postgresql
```

---

## 3. Custom User Authentication

Created a custom User model using `AbstractUser`.

Additional fields:

- Role
- Phone Number

User Roles:

- Patient
- Caregiver
- Admin

---

## 4. JWT Authentication

Implemented secure authentication using:

```
djangorestframework-simplejwt
```

Implemented APIs:

- User Registration
- Login
- Protected Profile API

JWT Features:

- Access Token
- Refresh Token
- Secure Protected APIs

---

## 5. Medicine Model

Medicine model created with required fields.

Stores:

- Medicine Name
- Dosage
- Frequency
- Medicine Type
- Start Date
- End Date
- Instructions

Each medicine is linked with a user.

---

## 6. Reminder Model

Reminder model created.

Stores:

- Reminder Date
- Reminder Time
- Reminder Status
- Medicine
- User

Each reminder belongs to a specific medicine and user.

---

## 7. Django Admin

Configured Django Admin for:

- Medicines
- Reminders

Admin Panel allows:

- View Records
- Add Records
- Update Records
- Delete Records

---

## 8. API Testing

All implemented APIs tested successfully using Postman.

Completed APIs:

### Register User

```
POST /api/accounts/register/
```

---

### Login

```
POST /api/token/
```

Returns:

- Access Token
- Refresh Token

---

### User Profile

```
GET /api/accounts/profile/
```

Requires:

```
Authorization:
Bearer <Access Token>
```

---

# 📷 Milestone 1 Output

✔ PostgreSQL Connected

✔ Django Admin Working

✔ JWT Authentication Working

✔ User Registration API Working

✔ Login API Working

✔ Protected Profile API Working

✔ Medicine Model Created

✔ Reminder Model Created

---

#  Security

Sensitive information such as:

- Database Password
- Secret Key

are stored securely using:

```
.env
```

and are excluded from version control.

---

# 📅 Milestone 1 Status

✅ Completed

---

#  Next Milestone

Upcoming development includes:

- React Frontend
- Medicine CRUD APIs
- Reminder CRUD APIs
- AI-based Medicine Reminder Engine
- Email/SMS Notifications
- Caregiver Dashboard
- Medication Tracking Dashboard

---

#  Developed By

**Anjali Tiwari**

B.Tech Information Technology

AI Internship Project

Project Title:

**PillSync – Intelligent Medicine Reminder and Medication Tracking Platform**
