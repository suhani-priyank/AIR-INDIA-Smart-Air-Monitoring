from flask import Flask, request
import mysql.connector

app = Flask(__name__)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="aditri_1428",
    database="pollution_db"
)

@app.route('/data', methods=['POST'])
def receive_data():

    try:
        mq2 = request.form.get('mq2')
        mq3 = request.form.get('mq3')
        mq135 = request.form.get('mq135')
        status = request.form.get('status')

        print("MQ2:", mq2)
        print("MQ3:", mq3)
        print("MQ135:", mq135)
        print("Status:", status)

        cursor = db.cursor()

        sql = """
        INSERT INTO sensor_data
        (mq2, mq3, mq135, aqi_status)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(sql, (mq2, mq3, mq135, status))
        db.commit()

        return "Data Stored", 200

    except Exception as e:
        print("ERROR:", e)
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)