# Mahi Local Event Data Manager

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Mahi is a checkpoint-driven, localized event management system designed for seamless participant check-ins, custom pathway enforcement, and flexible runtime data gathering. 

Engineered with portability and offline-first environments in mind, Mahi allows organizers to easily deploy a complete check-in infrastructure on a local laptop or desktop. Field operators can then securely connect to the central dashboard and perform data validation or input from their own mobile devices or PCs over a local area network (LAN/Wi-Fi), eliminating the need for constant cloud connectivity or complex infrastructure.

---

## Key Features

- **Offline-First & LAN Ready:** Easily bind to local network addresses (`0.0.0.0`) to let remote operators on the same network access the application via tablets, smartphones, or laptops.
- **Checkpoint-Driven Workflow:** Define dynamic paths and checkpoints that participants follow. Control sequential routing and check-in duplication settings per path or checkpoint.
- **Granular Data Isolation & Permissions:** Define custom data schemas per event (e.g., text, numeric, date, and boolean fields) and map them to individual checkpoints with read/write/fill permissions. Keep sensitive participant data private by only exposing fields to authorized operators at designated checkpoints.
- **Advanced Dynamic Resolution:** Automatically resolve data attributes from multiple sources, including global participant metadata, event-specific registration metadata, default values, or operator-entered check-in data.
- **Robust Import System:** Load participant directories directly from Excel/CSV spreadsheets using pandas. Features custom field mapping, duplicate detection, and automated validation.
- **Full History & Safe Deletion:** Built-in soft deletes (via `django-safedelete`) and auditing mechanisms (via `django-simple-history`) ensure that no operational data is lost and all modifications are tracked.
- **Persian Calendar & Localization Support:** Preconfigured with Farsi locale, Tehran timezone, and Jalali calendar date pickers using `jdatetime` and `jalali_core`.

---

## Core Entities & Architecture

The workflow of Mahi is modeled around the following core database components:

### 1. Events
The root operational entity representing a distinct gathering, session, or tournament. An event maintains its own state (active/inactive), start/stop timestamps, and registers its own set of participants and data schemas.

### 2. Paths
Workflows defined within an event. A path determines the sequence of checkpoints a participant should traverse.
- **Enforced Checkpoint Order:** When enabled, prevents a participant from checking in at a checkpoint if they haven't successfully checked in at preceding mandatory checkpoints.
- **Duplicate Prevention:** Configurable flags to reject or permit multiple check-ins along the same path.

### 3. Checkpoints
Distinct physical or logical stations managed by designated operator accounts. 
- Assigned to a specific path and ordered sequentially.
- Can be optionally marked as **mandatory** for path completion.
- Supports coordinates (Latitude/Longitude) to log operator locations.

### 4. Event Schemas & Checkpoint Schemas
Allows defining arbitrary database schemas at runtime:
- Supports text, numeric, date, and boolean field types.
- Checkpoint schemas bind specific fields to checkpoints, assigning granular access:
  - `can_view`: Determines if the operator can see the current value of the field.
  - `can_edit`: Allows editing of existing values.
  - `can_fill`: Prompts the operator to fill out the value during check-in.

### 5. Participant Directory (People)
The core pool of participants. Includes default attributes (first name, last name, phone number, birth date) alongside a dynamic `metadata` JSON field for arbitrary, indexable custom tags.

### 6. Check-ins & Check-in Data
Logs participant check-in events at checkpoints, validating path sequence logic and capturing schema-specific data slices at the moment of entry. All data modifications are fully version-controlled.

---

## Technical Stack

- **Framework:** [Django 5.2](https://docs.djangoproject.com/en/5.2/)
- **Data Wrangling:** [pandas](https://pandas.pydata.org/), [numpy](https://numpy.org/) (for spreadsheet processing)
- **Localization:** [jdatetime](https://github.com/khaledalhariri/jdatetime), [jalali_core](https://github.com/a-m-d/django-jalali-date)
- **Data Integrity:** [django-safedelete](https://github.com/makinacorpus/django-safedelete), [django-simple-history](https://github.com/jazzband/django-simple-history)
- **Database:** SQLite (default/development) or PostgreSQL (production-ready via `psycopg3` and `dj-database-url`)

---

## Getting Started

### Prerequisites
- Python 3.10+
- pip

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/mahi.git
   cd mahi
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Unix/macOS:
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory:
   ```ini
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
   SERVER_ADDRESS=http://192.168.1.100:8000
   # DATABASE_URL=postgres://user:password@localhost:5432/dbname
   ```
   *Replace `192.168.1.100` with the local IP address of your host laptop/PC to expose the application to other devices on your local Wi-Fi or LAN.*

5. **Initialize the Database:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

### Running on a Local Network (LAN)

To run the application and allow other devices (mobiles/tablets) to connect to your host:
```bash
python manage.py runserver 0.0.0.0:8000
```
Then, operators can access the app by navigating to `http://<YOUR_LAPTOP_IP>:8000` on their devices.

---

## Code Quality & Contributions

This project enforces strict standards to maintain codebase predictability and clean architecture. When making contributions, please keep the following guidelines in mind (as detailed in [CODE_STYLE.md](CODE_STYLE.md)):

- **Type Hints:** All parameter types and return types must be fully declared for all service functions and views. Avoid using `Any` where concrete models or `TypedDict` can be used.
- **Import Ordering:** Maintain consistent import blocks:
  1. Standard Library
  2. Django
  3. Third-party packages
  4. Local applications
- **Views & Services Separation:** Keep business logic, verification routines, and persistence-heavy tasks in **Services** (e.g., `CheckInWorkflowService`). Keep **Views** focused purely on request parsing, form-binding, and response dispatching.

---

## Project Structure

```text
├── mahi/                # Project configuration (settings, URLs, WSGI)
├── core/                # Shared utilities, base templates, and static assets
├── accounts/            # User authentication, roles, and global settings
├── events/              # Event, Path, Checkpoint, and Schema models & views
├── people/              # Participant profiles, bulk import, and filtering services
├── operations/          # Real-time check-in logging, workflow services, and dashboard
├── manage.py            # Django management CLI
└── requirements.txt     # Python dependencies
```

---

## Future Roadmap

- **Analytics Dashboard:** Graphical reports, completion rates, and checkpoint throughput metrics.
- **SMS Gateway Integration:** Dispatch real-time SMS notifications to participants upon checking in at designated checkpoints.
- **Automatic Local Discovery:** Zero-configuration network announcement to simplify device connections on local networks.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
