# Mahi Local Event Data Manager

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)

Mahi is a checkpoint-driven, localized event management system designed for participant check-ins, custom path configuration, and dynamic data collection. 

Engineered with portability and offline-first environments in mind, Mahi is optimized to run locally on a host laptop or desktop. Field operators can connect to the central application and perform check-ins or data entry from their mobile devices or PCs over a local area network (LAN/Wi-Fi), eliminating the need for constant cloud connectivity.

---

## Core Architecture & Execution Flow

Mahi models event workflows around a set of distinct database components and services:

### 1. Events, Paths, & Checkpoints
- **Events:** Root entities representing operational sessions that gather participant lists and associated schemas.
- **Paths:** User-defined workflows detailing how participants proceed. Configured with flags like `enforce_checkpoint_order` (restricting access to checkpoints out of order) and `allow_duplicate_checkin`.
- **Checkpoints:** Distinct stations managed by specific operator accounts. They contain Latitude/Longitude coordinates for location-tagging and specify schema permissions.

### 2. Workflow Validation (`CheckInValidationService`)
- Enforces pathway logic at runtime. If sequence order is enabled, it prevents checking in at a checkpoint if mandatory preceding checkpoints are incomplete.
- Screens check-ins to prevent unauthorized duplicates unless explicit bypasses are configured at the path or checkpoint levels.

### 3. Access-Controlled Data Schemas (`EventSchema` & `CheckpointSchema`)
- Organizers define data fields of various types (text, numbers, dates, boolean flags).
- Fields are mapped to specific checkpoints with granular capabilities:
  - `can_view`: Restricts visibility of existing field data to designated operators.
  - `can_edit`: Governs whether existing values can be overwritten at that station.
  - `can_fill`: Flags fields that operators are prompted to input during the check-in transaction.
- **Dynamic Field Resolution:** Resolves values dynamically from default settings, global participant profiles, event-specific registration metadata, or operator inputs.

### 4. Participant Imports (`PersonImportService`)
- Handles spreadsheet uploads using `pandas`.
- Performs character length validations, maps headers to internal fields, and serializes extra spreadsheet columns into unstructured, indexable JSON metadata.

---

## Technical Stack & Frontend Rendering

### Backend
- **Core Framework:** Django 5.2 (using Python 3.10+)
- **Database Layer:** Configurable via `dj-database-url`. Supports SQLite for local dev and PostgreSQL for production.
- **Data Integrity:** Soft deletes (`django-safedelete`) and complete historical audit logs (`django-simple-history`) are implemented globally.

### Frontend & Rendering
- **Interface Stack:** HTML, CSS, JavaScript, Alpine.js, and HTMX.
- **Real-Time Dynamic Rendering:** Templates leverage **Server-Sent Events (SSE)** to stream real-time updates directly to the operator interface without full page reloads.
- **Responsiveness:** Designed with a fluid layout using clamp typographies, flexible layouts, and touch-target adjustments to be fully responsive and optimized for mobile devices and tablets.

---

## Getting Started

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

4. **Environment Configuration:**
   Create a `.env` file in the root directory:
   ```ini
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
   SERVER_ADDRESS=http://192.168.1.100:8000
   ```
   *Note: Set your host laptop's local IP address (e.g., `192.168.1.100`) to let other operators access the application over Wi-Fi.*

5. **Initialize Database:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

### Local Network Deployment

Run the server bound to all network interfaces to allow local LAN access:
```bash
python manage.py runserver 0.0.0.0:8000
```
Operators can access the application by navigating to `http://<YOUR_IP>:8000` from their mobile devices or laptops. Code modifications should adhere to the project type-hinting and view-service separation rules in [CODE_STYLE.md](CODE_STYLE.md).

---

## Future Roadmap

- **Analytics Dashboard:** Graphical reports and checkpoint throughput metrics.
- **SMS Gateway Integration:** Dispatch real-time SMS notifications to participants upon checking in at designated checkpoints.
- **Automatic Local Discovery:** Zero-configuration network announcement to simplify device connections on local networks.
