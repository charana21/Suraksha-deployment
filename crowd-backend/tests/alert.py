# from twilio.rest import Client
# import json


# class WhatsAppTemplateTester:

#     def __init__(self):
#         print("[WhatsAppTemplateTester] Initialized")

#         # 🔹 Hard-coded Twilio credentials
#         self.account_sid = "AC_DUMMY_ACCOUNT_SID"
#         self.auth_token = "DUMMY_AUTH_TOKEN"

#         # 🔹 Twilio WhatsApp approved sender
#         self.from_number = "whatsapp:+918978877474"

#         # 🔹 User number from your MongoDB document
#         self.to_number = "whatsapp:+918341351959"

#         # 🔹 Template Content SID
#         self.content_sid = "HX215e7ed20fb1448c5408ae693205cdc1"

#         # 🔹 Create client
#         self.client = Client(self.account_sid, self.auth_token)

#     def send_template(self):

#         try:

#             # Hard-coded variables
#             variables = {
#                 "1": "Dev User",                # username
#                 "2": "12627",                   # train number
#                 "3": "14:30",                   # train time
#                 "4": "Running late by 25 minutes."
#             }

#             print("[WhatsApp] Sending template message...")

#             message = self.client.messages.create(
#                 from_=self.from_number,
#                 to=self.to_number,
#                 content_sid=self.content_sid,
#                 content_variables=json.dumps(variables)
#             )

#             print("✅ Message request sent successfully")
#             print("Message SID:", message.sid)

#             return True

#         except Exception as e:

#             print("❌ Error sending message")
#             print(e)

#             return False


# if __name__ == "__main__":

#     tester = WhatsAppTemplateTester()
#     result = tester.send_template()

#     print("Result:", result)