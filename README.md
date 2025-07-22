# Ledgerly: Transaction Tracker

This project is an MVP for a transaction tracking application, built for Ledgerly, a fictional fintech startup. It lets users view a list of transactions, import new ones from an external API, and manually add their own. The app maintains a running balance and includes various validations for transactions.

## Technologies Used

- **Backend**: Django 5.x, Python 3.10+
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla JS), Bootstrap 5
- **Containerization**: Docker, Docker Compose

## Features

- **Transaction Display**: Shows a paginated list of transactions, sorted newest to oldest, with their code, date, type, amount, and a running balance.
- **Balance Summary**: Displays the current total balance, updated in real-time.
- **External API Import**: Allows users to fetch transactions from an external API and store them in the local database.
- **Manual Transaction Addition**: Provides a Bootstrap modal form for users to manually add new deposit or expense transactions.
- **Backend Validations**:
  - Amount must be a positive number.
  - Adding an expense can't result in a negative total balance.
  - A daily limit of 200 expense transactions is enforced.
- **Dynamic UI Updates**: Uses AJAX for adding transactions, loading more data, and updating the balance.
- **Pagination**: Implements "Load More" functionality to fetch transactions in batches of 10.
- **Responsive Design**: Optimized for various screen sizes using Bootstrap 5.
- **Filtering**: Basic filtering by transaction type (deposit/expense/all).

## How to Run Locally with Docker Compose

Follow these steps to get the application running on your local machine using Docker Compose.

### Prerequisites

- **Docker Desktop**: Ensure Docker Desktop is installed and running on your system.

### Steps

1. **Clone the Repository**:
   ```bash
   git clone <your-repository-url>
   cd <your-project-directory>
   ```
2. **Build Docker Images:**:

Build the Docker images for your Django application and PostgreSQL database. This might take a few minutes the first time.

```bash
docker compose build
```

3. **Start Services:**
   Launch the Django and PostgreSQL services.
   ```bash
    docker compose up
   ```
4. **Access the Application:**
   The application should now be running and accessible in your web browser at:
   http://localhost:8000

5. **Running Tests:**

```bash
    docker compose exec web python manage.py test transactions
```

6. **Clean transactions upload from API:**

```bash
docker exec -it test001-web-1 python manage.py shell
```

```bash
from transactions.models import Transaction
Transaction.objects.all().delete()
```

```bash
exit()
```
