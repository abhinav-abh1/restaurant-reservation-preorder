# 🍽️ Restaurant Reservation & Pre-Order Management System

A full-stack web application built using **Flask** and **PostgreSQL** that allows users to reserve tables, pre-order food, make payments, and verify bookings using QR codes.

This project is developed as an **MCA academic final-year project** while following **industry-standard architecture and best practices**.

---

## 📌 Project Overview

Traditional restaurant systems handle table reservation and food ordering separately, causing inefficiencies and long waiting times.  
This system solves that problem by **combining table reservation and food pre-ordering into a single unified platform**, improving both customer experience and restaurant operations.

The application supports **three major roles**:

- **Admin**
- **Restaurant (Hotel)**
- **User (Customer)**

---

## 🎯 Objectives

- Simplify table reservation and food ordering
- Reduce customer waiting time
- Provide QR-based reservation and order verification
- Offer analytics for business decision-making
- Support premium users with priority services
- Build a secure, scalable, and modular system

---

## 🧑‍💻 Technology Stack

### Backend

- Python (Flask Framework)
- REST-based routing
- Session-based authentication

### Database

- PostgreSQL
- Normalized relational schema
- Secure query handling

### Frontend

- HTML5
- CSS3
- JavaScript (Vanilla)

### Tools & Utilities

- QR Code generation
- Analytics & reporting
- Payment workflow (logic-ready)
- Git & GitHub for version control

---

## 🧩 System Modules

### 👤 User Module

- User registration & login
- Restaurant browsing & filtering
- Table reservation
- Food pre-ordering during booking
- Online payment workflow
- QR code generation for verification
- Premium user features:
  - Priority booking
  - Special offers
  - Faster confirmations

---

### 🏨 Restaurant (Hotel) Module

- Restaurant registration
- Admin verification & approval
- Menu management
- Time-based food availability:
  - Breakfast
  - Lunch
  - Dinner
- Reservation slot management
- Order handling
- QR code verification for customers

---

### 🛠️ Admin Module

- Restaurant approval & rejection
- User management
- Booking & order monitoring
- Analytics dashboard:
  - Most ordered dishes
  - Peak booking times
  - Restaurant performance
- Report generation

---

## 🔄 System Workflow

1. User registers and logs in
2. User searches for restaurants
3. User selects date and time
4. User pre-orders food (optional)
5. Payment is processed
6. QR code is generated
7. User presents QR code at restaurant
8. Restaurant verifies QR code
9. Order is served

---

## 📊 Analytics & Reports

- Most popular dishes
- Peak reservation hours
- High-performing restaurants
- User activity insights
- Revenue analysis (logic-ready)

---

## 🗂️ Project Structure

```text
restaurant-reservation/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── routes/
│   ├── admin.py
│   ├── user.py
│   └── restaurant.py
│
├── models/
│   ├── user.py
│   ├── restaurant.py
│   └── booking.py
│
├── templates/
│   ├── admin/
│   ├── user/
│   └── restaurant/
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── uploads/          # ignored
├── qr_codes/         # ignored
└── venv/             # ignored
```
