import re 
from quart import Quart, jsonify, request
from quart_cors import cors

app = Quart(__name__)
app = cors(app, allow_origin=re.compile(r"http:\/\/localhost(:[0:9]+)?"))


@app.route("/", methods=["GET"])
async def health_check():
    return jsonify({"code": 200, "response": "backend service is up and running"})


@app.route("/api/v1/conversation", methods=["POST"])
async def conversation():
    data = await request.get_json()

    message = data.get('message')
    return jsonify({"data": f"received message: {message}"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3123)

# For local testing in powershell
'''
Invoke-WebRequest -Uri http://localhost:3123/api/v1/conversation `
                  -Method POST `
                  -Headers @{ "Content-Type" = "application/json" } `
                  -Body '{ "message": "I want to find out more about the technology sector" }'
'''
