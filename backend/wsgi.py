"""Entry point. Railway and `flask run` both look here."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
