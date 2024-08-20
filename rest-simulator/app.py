from flask import Flask, request, jsonify
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/v1/member/update', methods=['POST'])
def member_update():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.data  # raw data in case the Content-Type is not set correctly
        try:
            # Attempt to decode bytes to string
            data = data.decode('utf-8')
        except AttributeError:
            pass  # If data is already a string, ignore

    print(f"Received headers: {request.headers}")
    print(f"Received data: {data}")
    logger.info("Received data: %s", data)  # Logging instead of print
    # Simulate processing the data and returning a status
    response = {
        "status": "success",
        "message": "Member update processed",
        "received_data": data
    }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)