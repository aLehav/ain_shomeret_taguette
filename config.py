# This is the configuration file for Taguette
# It is a Python file, so you can use the full Python syntax

# Name of this server
NAME = "Ain Shomeret Taguette Server"

# Address and port to listen on
BIND_ADDRESS = "0.0.0.0"
PORT = 7465

# Base path of the application
BASE_PATH = "/"

# A unique secret key that will be used to sign cookies
SECRET_KEY = "8cy0XzMHAej8W5RGNz9uWJit6sHFZFP1dp3Ga7Uz"

# Database to use
# This is a SQLAlchemy connection URL; refer to their documentation for info
# https://docs.sqlalchemy.org/en/latest/core/engines.html
# If using SQLite3 on Unix, note the 4 slashes for an absolute path
# (keep 3 before a relative path)
DATABASE = "postgresql://short:4889461687651432@172.17.0.1:5432/taguette"

# Redis instance for live collaboration
# This is not required if using a single server, collaboration will still work
#REDIS_SERVER = 'redis://localhost:6379'

# Address to send system emails from
EMAIL = "adamlehavi@gmail.com"

# Terms of service (HTML file)
# TOS_FILE = 'tos.html'
# If set to None, no terms of service link will be displayed anywhere
TOS_FILE = None

# Extra footer at the bottom of every page
#EXTRA_FOOTER = """
#  | This instance of Taguette is managed by Example University.
#  Please <a href="mailto:it@example.org">email IT</a> with any questions.
#"""

# Default language
DEFAULT_LANGUAGE = 'en_US'

# SMTP server to use to send emails
MAIL_SERVER = {
    "ssl": False,
    "host": "localhost",
    "port": 25,
}

# Whether users must explicitly accept cookies before using the website
COOKIES_PROMPT = False

# Whether new users can create an account
REGISTRATION_ENABLED = True

# Whether users can import projects from SQLite3 files
SQLITE3_IMPORT_ENABLED = True

# Set this to true if you are behind a reverse proxy that sets the
# X-Forwarded-For header.
# Leave this at False if users are connecting to Taguette directly
X_HEADERS = False

# Time limits for converting documents
CONVERT_TO_HTML_TIMEOUT = 3 * 60  # 3min for importing document into Taguette
CONVERT_FROM_HTML_TIMEOUT = 3 * 60  # 3min for exporting from Taguette

# If you want to export metrics using Prometheus, set a port number here
#PROMETHEUS_LISTEN = "0.0.0.0:9101"

# If you want to report errors to Sentry, set your DSN here
#SENTRY_DSN = "https://<key>@sentry.io/<project>"
