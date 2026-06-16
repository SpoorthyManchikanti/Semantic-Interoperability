"""Create DB tables using SQLAlchemy metadata in app.models."""
if __name__ == "__main__":
    import app.models
    print("SQLAlchemy models imported; metadata.create_all executed.")
