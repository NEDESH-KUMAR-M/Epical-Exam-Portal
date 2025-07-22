from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def show_image():
    name = "1"  # Example name or fetch from GSheet if needed

    # Google Drive file ID
    file_id = "1NCSq1cO0Jkpjo96Aac9YuDSpps9jyNx0"
    photo_url = f"https://drive.google.com/thumbnail?id=1Kz1woYsXKtCwxyyNkWaQPJwF5sQh-gEI"

    html = f"""
    <html>
    <head><title>{name}'s Photo</title></head>
    <body>
        <h1>Hello, {name}</h1>
        <img src="{photo_url}" alt="Photo of {name}" width="300"/>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(debug=True)
