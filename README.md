# 🏦 Financial Banking Management System Using Python

A desktop-based Financial Banking Management System developed using Python, Tkinter, and SQLite. This application allows users to register accounts, deposit money, withdraw money, transfer funds, and view transaction history through a graphical user interface.

## 📌 Project Information

- **Project Name:** Financial Banking Management System
- **Language:** Python
- **Frontend:** Tkinter
- **Database:** SQLite
- **Database Connectivity:** sqlite3
- **Platform:** Windows
- **Project Type:** Desktop Application

## ✨ Features

### 1. Customer Management
- Register new customers.
- Automatically generate unique account numbers.
- Secure customer login.
- View and update customer information.
- Store customer details in an SQLite database.

### 2. Banking Operations
- Deposit money into an account.
- Withdraw money from an account.
- Transfer money between registered accounts.
- Check the current account balance.
- Prevent withdrawals exceeding the available balance.

### 3. Transaction Management
- View transaction history.
- Record deposits and withdrawals.
- Record incoming and outgoing transfers.
- Display transaction dates, amounts, descriptions, and reference numbers.
- Search and filter transactions.

### 4. Administrator Panel
- Create the first administrator account.
- Log in securely as an administrator.
- View registered customer accounts.
- Search customer records.
- Activate or deactivate accounts.
- View customer transaction histories.
- View basic banking statistics.

### 5. Security and Validation
- Password hashing.
- Parameterized SQL queries.
- Input validation.
- Database transaction handling for fund transfers.
- Error and success messages.
- Account status verification.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application logic |
| Tkinter | Graphical user interface |
| SQLite | Database storage |
| sqlite3 | Database connectivity |
| hashlib | Password hashing |
| secrets | Secure random value generation |

## 📂 Project Structure

```text
FinancialBankingSystem/
│
├── financial_banking_system.py
├── banking.db
└── README.md
```

**Note:** The `banking.db` file is generated automatically when the application starts. It stores customer accounts, account balances, transaction history, and administrator information.

## 💻 System Requirements

- Windows 10 or Windows 11.
- Python 3.10 or later recommended.
- Tkinter support in the Python installation.
- No additional third-party Python packages are required.

## 🚀 Installation and Execution

### Step 1: Install Python

Download Python from the official website:

https://www.python.org/downloads/

During installation on Windows, enable **Add Python to PATH**.

### Step 2: Download the Project

Download `financial_banking_system.py` and save it inside a folder named `FinancialBankingSystem`.

### Step 3: Open the Project Folder

Open the folder in Visual Studio Code or open Command Prompt and navigate to the project directory.

```bash
cd path\to\FinancialBankingSystem
```

Replace the example path with your actual project folder path.

### Step 4: Verify Python Installation

Run:

```bash
python --version
```

### Step 5: Run the Application

Execute:

```bash
python financial_banking_system.py
```

The Financial Banking Management System window should open.

## 🔐 Initial Administrator Setup

1. Launch the application.
2. Click **Create First Administrator**.
3. Enter an administrator username containing at least three characters.
4. Create a password containing at least ten characters.
5. Confirm the password.
6. Click **Create Administrator**.
7. Log in through the Administrator Login screen.

The first administrator must be created before administrator login is possible.

## 👤 Customer Registration

1. Open the application.
2. Click **Create New Customer Account**.
3. Enter your full name, email, phone number, address, and password.
4. Confirm your password.
5. Click **Register**.
6. Save the generated account number.
7. Return to the login screen and sign in.

A new customer account starts with a balance of ₹0.00.

## 💰 How to Test Banking Operations

### Deposit Money
1. Log in as a customer.
2. Click **Deposit Money**.
3. Enter a positive amount.
4. Confirm the transaction.
5. Check the updated balance.

### Withdraw Money
1. Click **Withdraw Money**.
2. Enter an amount within your available balance.
3. Confirm the transaction.
4. Check the updated balance.

### Transfer Funds
1.


