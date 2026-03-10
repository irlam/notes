from app import create_app

app = create_app()

# Passenger expects a WSGI callable; expose it as "application"
application = app
