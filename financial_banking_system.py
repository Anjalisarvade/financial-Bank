

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from decimal import Decimal, InvalidOperation

APP_TITLE = "Financial Banking Management System"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banking.db")
BG = "#f3f6fb"
NAVY = "#16324f"
BLUE = "#2563eb"
GREEN = "#16803c"
RED = "#b42318"
WHITE = "#ffffff"
TEXT = "#172b4d"


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password, salt=None):
    """PBKDF2 password hash using a random salt."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000
        ).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False


def money_to_cents(value):
    try:
        amount = Decimal(value.strip())
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
            return None
        cents = int(amount * 100)
        return cents if cents > 0 else None
    except (InvalidOperation, AttributeError, ValueError):
        return None


def format_money(cents):
    return f"₹{cents / 100:,.2f}"


class BankingDB:
    def __init__(self, path=DB_FILE):
        self.path = path
        self.initialize()

    def connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def initialize(self):
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    account_number TEXT NOT NULL UNIQUE,
                    account_type TEXT NOT NULL DEFAULT 'Savings',
                    account_status TEXT NOT NULL DEFAULT 'Active'
                        CHECK(account_status IN ('Active', 'Inactive')),
                    created_date TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(user_id),
                    account_number TEXT NOT NULL UNIQUE,
                    account_type TEXT NOT NULL DEFAULT 'Savings',
                    balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
                    created_date TEXT NOT NULL,
                    account_status TEXT NOT NULL DEFAULT 'Active'
                        CHECK(account_status IN ('Active', 'Inactive'))
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_number TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK(amount > 0),
                    transaction_date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reference_number TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_transactions_account
                ON transactions(account_number, transaction_id DESC);

                CREATE TABLE IF NOT EXISTS admins (
                    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_date TEXT NOT NULL
                );
            """)

    def create_user(self, name, email, phone, address, password):
        created = now_text()
        account_number = "10" + "".join(secrets.choice("0123456789") for _ in range(10))
        for _ in range(10):
            try:
                with self.connect() as con:
                    con.execute("BEGIN IMMEDIATE")
                    con.execute("""
                        INSERT INTO users
                        (full_name,email,phone,address,password_hash,account_number,
                         account_type,account_status,created_date)
                        VALUES (?,?,?,?,?,?,'Savings','Active',?)
                    """, (name, email, phone, address, hash_password(password),
                          account_number, created))
                    user_id = con.execute(
                        "SELECT user_id FROM users WHERE email=?", (email,)
                    ).fetchone()["user_id"]
                    con.execute("""
                        INSERT INTO accounts
                        (user_id,account_number,account_type,balance,created_date,account_status)
                        VALUES (?,?,'Savings',0,?,'Active')
                    """, (user_id, account_number, created))
                return account_number
            except sqlite3.IntegrityError as exc:
                if "account_number" in str(exc).lower():
                    account_number = "10" + "".join(
                        secrets.choice("0123456789") for _ in range(10)
                    )
                    continue
                raise
        raise RuntimeError("Could not generate a unique account number. Please retry.")

    def get_user_by_email(self, email):
        with self.connect() as con:
            return con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    def get_account(self, account_number):
        with self.connect() as con:
            return con.execute("""
                SELECT a.*, u.full_name, u.email, u.phone, u.address, u.user_id
                FROM accounts a JOIN users u ON u.user_id=a.user_id
                WHERE a.account_number=?
            """, (account_number,)).fetchone()

    def login_user(self, email, password):
        row = self.get_user_by_email(email)
        if row and verify_password(password, row["password_hash"]):
            if row["account_status"] != "Active":
                return None, "This account is inactive. Contact the administrator."
            return row, None
        return None, "Invalid email or password."

    def admin_exists(self):
        with self.connect() as con:
            return con.execute("SELECT 1 FROM admins LIMIT 1").fetchone() is not None

    def create_admin(self, username, password):
        with self.connect() as con:
            con.execute(
                "INSERT INTO admins(username,password_hash,created_date) VALUES(?,?,?)",
                (username, hash_password(password), now_text())
            )

    def login_admin(self, username, password):
        with self.connect() as con:
            row = con.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        return row if row and verify_password(password, row["password_hash"]) else None

    def summary(self, account_number):
        with self.connect() as con:
            row = con.execute("""
                SELECT a.balance,
                    COALESCE(SUM(CASE WHEN t.transaction_type='Deposit' THEN t.amount ELSE 0 END),0) deposits,
                    COALESCE(SUM(CASE WHEN t.transaction_type='Withdrawal' THEN t.amount ELSE 0 END),0) withdrawals
                FROM accounts a LEFT JOIN transactions t ON t.account_number=a.account_number
                WHERE a.account_number=? GROUP BY a.account_number
            """, (account_number,)).fetchone()
            return row

    def add_transaction(self, con, account, kind, cents, description, reference):
        con.execute("""
            INSERT INTO transactions
            (account_number,transaction_type,amount,transaction_date,description,reference_number)
            VALUES (?,?,?,?,?,?)
        """, (account, kind, cents, now_text(), description, reference))

    def deposit(self, account_number, cents):
        ref = secrets.token_hex(8).upper()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT balance,account_status FROM accounts WHERE account_number=?",
                (account_number,)
            ).fetchone()
            if not row or row["account_status"] != "Active":
                raise ValueError("This account is not active.")
            con.execute("UPDATE accounts SET balance=balance+? WHERE account_number=?",
                        (cents, account_number))
            self.add_transaction(con, account_number, "Deposit", cents, "Cash deposit", ref)
        return ref

    def withdraw(self, account_number, cents):
        ref = secrets.token_hex(8).upper()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT balance,account_status FROM accounts WHERE account_number=?",
                (account_number,)
            ).fetchone()
            if not row or row["account_status"] != "Active":
                raise ValueError("This account is not active.")
            if row["balance"] < cents:
                raise ValueError("Insufficient balance.")
            con.execute("UPDATE accounts SET balance=balance-? WHERE account_number=?",
                        (cents, account_number))
            self.add_transaction(con, account_number, "Withdrawal", cents, "Cash withdrawal", ref)
        return ref

    def transfer(self, sender, recipient, cents):
        if sender == recipient:
            raise ValueError("You cannot transfer money to your own account.")
        ref = secrets.token_hex(8).upper()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute("""
                SELECT account_number,balance,account_status FROM accounts
                WHERE account_number IN (?,?)
            """, (sender, recipient)).fetchall()
            accounts = {r["account_number"]: r for r in rows}
            if sender not in accounts:
                raise ValueError("Sender account not found.")
            if recipient not in accounts:
                raise ValueError("Recipient account number not found.")
            if accounts[sender]["account_status"] != "Active":
                raise ValueError("Your account is inactive.")
            if accounts[recipient]["account_status"] != "Active":
                raise ValueError("Recipient account is inactive.")
            if accounts[sender]["balance"] < cents:
                raise ValueError("Insufficient balance.")
            con.execute("UPDATE accounts SET balance=balance-? WHERE account_number=?",
                        (cents, sender))
            con.execute("UPDATE accounts SET balance=balance+? WHERE account_number=?",
                        (cents, recipient))
            self.add_transaction(con, sender, "Transfer Out", cents,
                                 f"Transfer to {recipient}", ref)
            self.add_transaction(con, recipient, "Transfer In", cents,
                                 f"Transfer from {sender}", ref)
        return ref

    def transactions(self, account_number, kind="All", search=""):
        sql = "SELECT * FROM transactions WHERE account_number=?"
        args = [account_number]
        if kind != "All":
            sql += " AND transaction_type=?"
            args.append(kind)
        if search.strip():
            sql += " AND (description LIKE ? OR reference_number LIKE ? OR transaction_date LIKE ?)"
            needle = "%" + search.strip() + "%"
            args.extend([needle, needle, needle])
        sql += " ORDER BY transaction_id DESC"
        with self.connect() as con:
            return con.execute(sql, args).fetchall()

    def update_profile(self, user_id, name, phone, address):
        with self.connect() as con:
            con.execute("UPDATE users SET full_name=?,phone=?,address=? WHERE user_id=?",
                        (name, phone, address, user_id))

    def admin_accounts(self, search=""):
        sql = """
            SELECT u.user_id,u.full_name,u.email,u.phone,u.account_number,
                   u.account_status,u.created_date,a.balance,a.account_type
            FROM users u JOIN accounts a ON a.user_id=u.user_id
        """
        args = []
        if search.strip():
            term = "%" + search.strip() + "%"
            sql += """ WHERE u.full_name LIKE ? OR u.email LIKE ?
                       OR u.account_number LIKE ? OR u.phone LIKE ?"""
            args = [term, term, term, term]
        sql += " ORDER BY u.user_id DESC"
        with self.connect() as con:
            return con.execute(sql, args).fetchall()

    def set_account_status(self, account_number, status):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE users SET account_status=? WHERE account_number=?",
                        (status, account_number))
            con.execute("UPDATE accounts SET account_status=? WHERE account_number=?",
                        (status, account_number))

    def admin_stats(self):
        with self.connect() as con:
            users = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
            total = con.execute("SELECT COALESCE(SUM(balance),0) n FROM accounts").fetchone()["n"]
            deposits = con.execute(
                "SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE transaction_type='Deposit'"
            ).fetchone()["n"]
            withdrawals = con.execute(
                "SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE transaction_type='Withdrawal'"
            ).fetchone()["n"]
            return users, total, deposits, withdrawals

    def all_transactions(self, account_number):
        return self.transactions(account_number)


class BankingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1080x700")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.db = BankingDB()
        self.current_user = None
        self.current_admin = None
        self._style()
        self.show_login()

    def _style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground=NAVY)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 11), foreground="#526581")
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("Primary.TButton", background=BLUE, foreground=WHITE)
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=27)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def header(self, title, subtitle=None):
        frame = ttk.Frame(self, padding=(28, 22, 28, 12))
        frame.pack(fill="x")
        ttk.Label(frame, text=title, style="Title.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(frame, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))

    def field(self, parent, label, show=None, width=38):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x", pady=6)
        ttk.Label(wrapper, text=label).pack(anchor="w", pady=(0, 3))
        entry = ttk.Entry(wrapper, width=width, show=show)
        entry.pack(fill="x")
        return entry

    def show_login(self):
        self.current_user = None
        self.current_admin = None
        self.clear()
        self.header("Welcome to SecureBank", "Financial Banking Management System • Educational demo")
        card = ttk.Frame(self, padding=28)
        card.pack(pady=15)
        ttk.Label(card, text="Customer Login", font=("Segoe UI", 15, "bold"),
                  background=BG, foreground=NAVY).pack(anchor="w", pady=(0, 12))
        self.login_email = self.field(card, "Email address")
        self.login_password = self.field(card, "Password", show="*")
        ttk.Button(card, text="Login", style="Primary.TButton",
                   command=self.customer_login).pack(fill="x", pady=(12, 6))
        ttk.Button(card, text="Create New Customer Account",
                   command=self.show_register).pack(fill="x", pady=4)
        ttk.Button(card, text="Administrator Login", command=self.show_admin_login).pack(fill="x", pady=4)
        ttk.Button(card, text="Create First Administrator", command=self.show_create_admin).pack(fill="x", pady=4)
        ttk.Label(self, text="Demo only. Do not use real passwords or real funds.",
                  foreground=RED).pack(pady=10)

    def customer_login(self):
        email = self.login_email.get().strip().lower()
        password = self.login_password.get()
        if not email or not password:
            messagebox.showerror("Missing information", "Enter your email and password.")
            return
        try:
            user, error = self.db.login_user(email, password)
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", f"Could not log in:\n{exc}")
            return
        if error:
            messagebox.showerror("Login failed", error)
            return
        self.current_user = user
        self.show_dashboard()

    def show_register(self):
        self.clear()
        self.header("Create Customer Account", "Enter your details to open a demo savings account.")
        form = ttk.Frame(self, padding=(30, 8))
        form.pack(fill="both", expand=True)
        self.reg_name = self.field(form, "Full name")
        self.reg_email = self.field(form, "Email address")
        self.reg_phone = self.field(form, "Phone number")
        self.reg_address = self.field(form, "Address")
        self.reg_password = self.field(form, "Password (at least 8 characters)", show="*")
        self.reg_confirm = self.field(form, "Confirm password", show="*")
        buttons = ttk.Frame(form)
        buttons.pack(fill="x", pady=12)
        ttk.Button(buttons, text="Register", style="Primary.TButton",
                   command=self.register_customer).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Back to Login", command=self.show_login).pack(side="left")

    def register_customer(self):
        name = self.reg_name.get().strip()
        email = self.reg_email.get().strip().lower()
        phone = self.reg_phone.get().strip()
        address = self.reg_address.get().strip()
        password = self.reg_password.get()
        confirm = self.reg_confirm.get()
        if not all([name, email, phone, address, password, confirm]):
            messagebox.showerror("Validation error", "Please fill in every field.")
            return
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            messagebox.showerror("Validation error", "Enter a valid email address.")
            return
        if not re.fullmatch(r"[0-9+()\- ]{7,20}", phone):
            messagebox.showerror("Validation error", "Enter a valid phone number (7–20 characters).")
            return
        if len(password) < 8:
            messagebox.showerror("Validation error", "Password must contain at least 8 characters.")
            return
        if password != confirm:
            messagebox.showerror("Validation error", "Passwords do not match.")
            return
        try:
            account = self.db.create_user(name, email, phone, address, password)
        except sqlite3.IntegrityError:
            messagebox.showerror("Registration failed", "An account with this email already exists.")
            return
        except (sqlite3.Error, RuntimeError) as exc:
            messagebox.showerror("Registration failed", str(exc))
            return
        messagebox.showinfo("Registration successful",
                            f"Your account was created successfully.\nAccount number: {account}\nOpening balance: ₹0.00")
        self.show_login()

    def show_dashboard(self):
        user = self.current_user
        if not user:
            self.show_login()
            return
        account = self.db.get_account(user["account_number"])
        if not account:
            messagebox.showerror("Error", "Account details could not be found.")
            self.show_login()
            return
        self.clear()
        top = ttk.Frame(self, padding=(26, 18))
        top.pack(fill="x")
        ttk.Label(top, text=f"Hello, {account['full_name']}", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")
        ttk.Label(self, text=f"Account number: {account['account_number']}   •   Status: {account['account_status']}",
                  background=BG, foreground="#526581", font=("Segoe UI", 10)).pack(anchor="w", padx=28)
        summary = self.db.summary(account["account_number"])
        cards = ttk.Frame(self, padding=(24, 16))
        cards.pack(fill="x")
        self.stat_card(cards, "Available Balance", format_money(summary["balance"]), NAVY, 0)
        self.stat_card(cards, "Total Deposits", format_money(summary["deposits"]), GREEN, 1)
        self.stat_card(cards, "Total Withdrawals", format_money(summary["withdrawals"]), RED, 2)
        actions = ttk.LabelFrame(self, text="Banking Services", padding=16)
        actions.pack(fill="x", padx=26, pady=8)
        action_items = [
            ("Deposit Money", self.deposit_dialog),
            ("Withdraw Money", self.withdraw_dialog),
            ("Transfer Funds", self.transfer_dialog),
            ("Transaction History", self.show_transactions),
            ("Account Details", self.show_profile),
        ]
        for i, (label, command) in enumerate(action_items):
            ttk.Button(actions, text=label, command=command).grid(
                row=i // 3, column=i % 3, padx=8, pady=8, sticky="ew"
            )
        for i in range(3):
            actions.columnconfigure(i, weight=1)
        recent_frame = ttk.LabelFrame(self, text="Recent Transactions", padding=10)
        recent_frame.pack(fill="both", expand=True, padx=26, pady=(4, 18))
        tree = self.make_tree(recent_frame, [
            ("transaction_id", "ID", 55), ("transaction_type", "Type", 115),
            ("amount", "Amount", 120), ("transaction_date", "Date / Time", 165),
            ("description", "Description", 300)
        ])
        for row in self.db.transactions(account["account_number"])[:6]:
            tree.insert("", "end", values=(
                row["transaction_id"], row["transaction_type"], format_money(row["amount"]),
                row["transaction_date"], row["description"]
            ))

    def stat_card(self, parent, title, value, foreground, column):
        card = tk.Frame(parent, bg=WHITE, highlightbackground="#d9e2f0", highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=6, pady=4)
        parent.columnconfigure(column, weight=1)
        tk.Label(card, text=title, bg=WHITE, fg="#526581",
                 font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(card, text=value, bg=WHITE, fg=foreground,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=14, pady=(0, 12))

    def make_tree(self, parent, columns):
        keys = [c[0] for c in columns]
        tree = ttk.Treeview(parent, columns=keys, show="headings")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, minwidth=45, anchor="w")
        yscroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.pack(side="top", fill="both", expand=True)
        xscroll.pack(side="bottom", fill="x")
        yscroll.pack(side="right", fill="y")
        return tree

    def transaction_amount_dialog(self, title, operation):
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        box = ttk.Frame(win, padding=24)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text=title, font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        entry = self.field(box, "Amount in ₹ (maximum 2 decimal places)")
        def submit():
            cents = money_to_cents(entry.get())
            if cents is None:
                messagebox.showerror("Invalid amount", "Enter an amount greater than zero with at most 2 decimal places.", parent=win)
                return
            try:
                if operation == "deposit":
                    ref = self.db.deposit(self.current_user["account_number"], cents)
                    success = f"Deposit completed: {format_money(cents)}"
                else:
                    ref = self.db.withdraw(self.current_user["account_number"], cents)
                    success = f"Withdrawal completed: {format_money(cents)}"
            except (ValueError, sqlite3.Error) as exc:
                messagebox.showerror("Transaction failed", str(exc), parent=win)
                return
            win.destroy()
            messagebox.showinfo("Success", f"{success}\nReference: {ref}")
            self.show_dashboard()
        ttk.Button(box, text="Confirm", style="Primary.TButton", command=submit).pack(fill="x", pady=(12, 4))
        ttk.Button(box, text="Cancel", command=win.destroy).pack(fill="x")

    def deposit_dialog(self):
        self.transaction_amount_dialog("Deposit Money", "deposit")

    def withdraw_dialog(self):
        self.transaction_amount_dialog("Withdraw Money", "withdraw")

    def transfer_dialog(self):
        win = tk.Toplevel(self)
        win.title("Transfer Funds")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        box = ttk.Frame(win, padding=24)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Transfer Funds", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        recipient = self.field(box, "Recipient account number")
        amount = self.field(box, "Amount in ₹ (maximum 2 decimal places)")
        def submit():
            target = recipient.get().strip()
            cents = money_to_cents(amount.get())
            if not target:
                messagebox.showerror("Validation error", "Enter the recipient account number.", parent=win)
                return
            if cents is None:
                messagebox.showerror("Invalid amount", "Enter an amount greater than zero with at most 2 decimal places.", parent=win)
                return
            try:
                ref = self.db.transfer(self.current_user["account_number"], target, cents)
            except (ValueError, sqlite3.Error) as exc:
                messagebox.showerror("Transfer failed", str(exc), parent=win)
                return
            win.destroy()
            messagebox.showinfo("Transfer successful",
                                f"Transferred {format_money(cents)} to account {target}.\nReference: {ref}")
            self.show_dashboard()
        ttk.Button(box, text="Transfer", style="Primary.TButton", command=submit).pack(fill="x", pady=(12, 4))
        ttk.Button(box, text="Cancel", command=win.destroy).pack(fill="x")

    def show_transactions(self):
        account_number = self.current_user["account_number"]
        self.clear()
        top = ttk.Frame(self, padding=(24, 20))
        top.pack(fill="x")
        ttk.Label(top, text="Transaction History", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Back to Dashboard", command=self.show_dashboard).pack(side="right")
        filters = ttk.Frame(self, padding=(24, 4))
        filters.pack(fill="x")
        ttk.Label(filters, text="Type:").pack(side="left", padx=(0, 5))
        kind = ttk.Combobox(filters, values=[
            "All", "Deposit", "Withdrawal", "Transfer Out", "Transfer In"
        ], state="readonly", width=16)
        kind.set("All")
        kind.pack(side="left", padx=(0, 12))
        ttk.Label(filters, text="Search:").pack(side="left", padx=(0, 5))
        search = ttk.Entry(filters, width=30)
        search.pack(side="left", padx=(0, 8))
        table_frame = ttk.Frame(self, padding=(24, 12))
        table_frame.pack(fill="both", expand=True)
        tree = self.make_tree(table_frame, [
            ("transaction_id", "ID", 55), ("transaction_type", "Type", 110),
            ("amount", "Amount", 110), ("transaction_date", "Date / Time", 165),
            ("description", "Description", 280), ("reference_number", "Reference", 140)
        ])
        def refresh(*_):
            tree.delete(*tree.get_children())
            try:
                rows = self.db.transactions(account_number, kind.get(), search.get())
                for row in rows:
                    tree.insert("", "end", values=(
                        row["transaction_id"], row["transaction_type"], format_money(row["amount"]),
                        row["transaction_date"], row["description"], row["reference_number"]
                    ))
            except sqlite3.Error as exc:
                messagebox.showerror("Error", str(exc))
        ttk.Button(filters, text="Search", command=refresh).pack(side="left")
        kind.bind("<<ComboboxSelected>>", refresh)
        search.bind("<Return>", refresh)
        refresh()

    def show_profile(self):
        user = self.current_user
        self.clear()
        self.header("Account Details", "Review or update your contact information.")
        account = self.db.get_account(user["account_number"])
        form = ttk.Frame(self, padding=(30, 8))
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=f"Account number: {account['account_number']}").pack(anchor="w", pady=5)
        ttk.Label(form, text=f"Account type: {account['account_type']}").pack(anchor="w", pady=5)
        ttk.Label(form, text=f"Status: {account['account_status']}").pack(anchor="w", pady=5)
        ttk.Label(form, text=f"Email: {account['email']} (cannot be changed here)").pack(anchor="w", pady=5)
        name = self.field(form, "Full name")
        name.insert(0, account["full_name"])
        phone = self.field(form, "Phone number")
        phone.insert(0, account["phone"])
        address = self.field(form, "Address")
        address.insert(0, account["address"])
        buttons = ttk.Frame(form)
        buttons.pack(fill="x", pady=12)
        def save():
            n, p, a = name.get().strip(), phone.get().strip(), address.get().strip()
            if not n or not a or not re.fullmatch(r"[0-9+()\- ]{7,20}", p):
                messagebox.showerror("Validation error", "Enter a name, address, and valid phone number.")
                return
            try:
                self.db.update_profile(user["user_id"], n, p, a)
                self.current_user = self.db.get_user_by_email(account["email"])
            except sqlite3.Error as exc:
                messagebox.showerror("Update failed", str(exc))
                return
            messagebox.showinfo("Saved", "Your details have been updated.")
            self.show_dashboard()
        ttk.Button(buttons, text="Save Changes", style="Primary.TButton", command=save).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Back to Dashboard", command=self.show_dashboard).pack(side="left")

    def show_admin_login(self):
        self.clear()
        self.header("Administrator Login", "Restricted access for system administration.")
        form = ttk.Frame(self, padding=28)
        form.pack(pady=15)
        username = self.field(form, "Admin username")
        password = self.field(form, "Admin password", show="*")
        def login():
            if not username.get().strip() or not password.get():
                messagebox.showerror("Missing information", "Enter username and password.")
                return
            try:
                admin = self.db.login_admin(username.get().strip(), password.get())
            except sqlite3.Error as exc:
                messagebox.showerror("Database error", str(exc))
                return
            if not admin:
                messagebox.showerror("Login failed", "Invalid administrator credentials.")
                return
            self.current_admin = admin
            self.show_admin_dashboard()
        ttk.Button(form, text="Login", style="Primary.TButton", command=login).pack(fill="x", pady=(12, 5))
        ttk.Button(form, text="Back", command=self.show_login).pack(fill="x")

    def show_create_admin(self):
        if self.db.admin_exists():
            messagebox.showinfo("Administrator already exists",
                                "An administrator account already exists. Please use Administrator Login.")
            return
        self.clear()
        self.header("Create First Administrator", "Only available before the first administrator is created.")
        form = ttk.Frame(self, padding=28)
        form.pack(pady=10)
        username = self.field(form, "Choose admin username")
        password = self.field(form, "Choose admin password (at least 10 characters)", show="*")
        confirm = self.field(form, "Confirm admin password", show="*")
        def create():
            u, p, c = username.get().strip(), password.get(), confirm.get()
            if not u or len(u) < 3:
                messagebox.showerror("Validation error", "Username must contain at least 3 characters.")
                return
            if len(p) < 10:
                messagebox.showerror("Validation error", "Admin password must contain at least 10 characters.")
                return
            if p != c:
                messagebox.showerror("Validation error", "Passwords do not match.")
                return
            try:
                self.db.create_admin(u, p)
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "That administrator username already exists.")
                return
            except sqlite3.Error as exc:
                messagebox.showerror("Error", str(exc))
                return
            messagebox.showinfo("Success", "Administrator account created. Please log in.")
            self.show_admin_login()
        ttk.Button(form, text="Create Administrator", style="Primary.TButton", command=create).pack(fill="x", pady=(12, 5))
        ttk.Button(form, text="Back", command=self.show_login).pack(fill="x")

    def show_admin_dashboard(self):
        if not self.current_admin:
            self.show_login()
            return
        self.clear()
        top = ttk.Frame(self, padding=(24, 18))
        top.pack(fill="x")
        ttk.Label(top, text="Administrator Dashboard", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")
        users, total, deposits, withdrawals = self.db.admin_stats()
        cards = ttk.Frame(self, padding=(20, 8))
        cards.pack(fill="x")
        self.stat_card(cards, "Customer Accounts", str(users), NAVY, 0)
        self.stat_card(cards, "Total Current Balances", format_money(total), GREEN, 1)
        self.stat_card(cards, "Recorded Deposits", format_money(deposits), BLUE, 2)
        self.stat_card(cards, "Recorded Withdrawals", format_money(withdrawals), RED, 3)
        controls = ttk.Frame(self, padding=(24, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="Search customers:").pack(side="left", padx=(0, 6))
        search = ttk.Entry(controls, width=35)
        search.pack(side="left", padx=(0, 8))
        table_frame = ttk.Frame(self, padding=(24, 4))
        table_frame.pack(fill="both", expand=True)
        tree = self.make_tree(table_frame, [
            ("account_number", "Account Number", 135), ("full_name", "Customer", 160),
            ("email", "Email", 200), ("phone", "Phone", 115),
            ("balance", "Balance", 110), ("account_status", "Status", 85),
            ("created_date", "Created", 145)
        ])
        def refresh(*_):
            tree.delete(*tree.get_children())
            for row in self.db.admin_accounts(search.get()):
                tree.insert("", "end", values=(
                    row["account_number"], row["full_name"], row["email"], row["phone"],
                    format_money(row["balance"]), row["account_status"], row["created_date"]
                ))
        def selected_account():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Select account", "Select a customer account in the table first.")
                return None
            return tree.item(selected[0], "values")[0]
        def toggle_status():
            account = selected_account()
            if not account:
                return
            row = self.db.get_account(account)
            new_status = "Inactive" if row["account_status"] == "Active" else "Active"
            if not messagebox.askyesno("Confirm", f"Set account {account} to {new_status}?"):
                return
            try:
                self.db.set_account_status(account, new_status)
            except sqlite3.Error as exc:
                messagebox.showerror("Update failed", str(exc))
                return
            refresh()
            messagebox.showinfo("Updated", f"Account status changed to {new_status}.")
        def view_transactions():
            account = selected_account()
            if not account:
                return
            rows = self.db.all_transactions(account)
            win = tk.Toplevel(self)
            win.title(f"Transactions for {account}")
            win.geometry("850x420")
            frame = ttk.Frame(win, padding=12)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=f"Transactions for account {account}",
                      font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
            table = self.make_tree(frame, [
                ("transaction_id", "ID", 50), ("transaction_type", "Type", 100),
                ("amount", "Amount", 100), ("transaction_date", "Date / Time", 160),
                ("description", "Description", 250), ("reference_number", "Reference", 130)
            ])
            for row in rows:
                table.insert("", "end", values=(
                    row["transaction_id"], row["transaction_type"], format_money(row["amount"]),
                    row["transaction_date"], row["description"], row["reference_number"]
                ))
        ttk.Button(controls, text="Search", command=refresh).pack(side="left", padx=3)
        ttk.Button(controls, text="Refresh", command=refresh).pack(side="left", padx=3)
        ttk.Button(controls, text="Activate / Deactivate Selected", command=toggle_status).pack(side="left", padx=3)
        ttk.Button(controls, text="View Selected Transactions", command=view_transactions).pack(side="left", padx=3)
        search.bind("<Return>", refresh)
        refresh()


if __name__ == "__main__":
    try:
        app = BankingApp()
        app.mainloop()
    except sqlite3.Error as exc:
        messagebox.showerror("Database startup error", f"Could not initialize banking.db:\n{exc}")
        raise
