import json
import boto3
import base64
import random
import string
import time
from decimal import *
import cv2


def OTP(stringLength=6):
    """
    OTP
    Credit: https://pynative.com/python-generate-random-string/
    """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

def get_database(table, key, lookup_val):
    db_client = boto3.client('dynamodb')
    db_response = db_client.get_item(
        TableName= table,
        Key={
            key: {"S": lookup_val}
        },
    )
    return db_response

def send_message(phone, text_message):
    sns_client = boto3.client('sns')
    sns_client.publish(
        PhoneNumber="+1" + phone,
        Message=text_message,
        Subject='Smartdoor Secure (Knock Knock)'
    )


def put_record_passcodes(table, faceID, OTP):
    # Put record in database
    item = {}
    item['access-code'] = OTP
    item['faceId'] = faceID
    expireTimestamp = int(time.time() + 300)
    item['ttl'] = expireTimestamp
    table.put_item(
       Item=item
    )

def put_record_phones(table, phone):
    # Put record in database
    item = {}
    item['phone-number'] = phone
    expireTimestamp = int(time.time() + 60)
    item['ttl'] = expireTimestamp
    table.put_item(
       Item=item
    )

def extract_frame(bucket_name):
    hls_stream_ARN = "arn:aws:kinesisvideo:us-east-1:423421644306:stream/smartdoorvideostream/1573843218757"

    STREAM_NAME = "smartdoorvideostream"
    kvs = boto3.client("kinesisvideo")

    # Grab the endpoint fVeryFirstrom GetDataEndpoint
    endpoint = kvs.get_data_endpoint(
        APIName="GET_HLS_STREAMING_SESSION_URL",
        StreamARN=hls_stream_ARN
    )['DataEndpoint']


    # Grab the HLS Stream URL from the endpoint
    kvam = boto3.client("kinesis-video-archived-media", endpoint_url=endpoint)
    url = kvam.get_hls_streaming_session_url(
        StreamName=STREAM_NAME,
        PlaybackMode="LIVE"
    )['HLSStreamingSessionURL']

    fname = str(int(time.time())) + '_frame.jpg'

    vcap = cv2.VideoCapture(url)
    ret, frame = vcap.read()

    cv2.imwrite('/tmp/'+fname, frame)
    s3_client = boto3.client('s3')
    s3_client.upload_file(
        '/tmp/'+fname,
        bucket_name, # replace with your bucket name
        fname
    )

    vcap.release()
    return fname


def spam_control(phone):
    response_phones = get_database('phones', 'phone-number', phone)
    if not('Item' not in response_phones.keys() or int(response_phones['Item']['ttl']['N'])  < int(time.time())):
        return True

    return False

def lambda_handler(event, context):

    for record in event['Records']:
        payload = base64.b64decode(record['kinesis']['data']).decode('utf-8')
        rek = json.loads(payload)

        dynamodb = boto3.resource('dynamodb')

        if len(rek['FaceSearchResponse']) == 0:
            # No face found
            return {
                'statusCode': 200,
                'body': json.dumps('No face found')
            }

        if len(rek['FaceSearchResponse'][0]['MatchedFaces']) == 0:
            # No match
            # Send link to WP1

            # Hard-coded
            bucket_name = "smart-door-b1"
            owner_phone = "8605157641"

            if spam_control(owner_phone):
                return {
                    'statusCode': 200,
                    'body': json.dumps('Spam control activated')
                }

            # Extract frame
            filename = extract_frame(bucket_name)

            # Put phone in database
            table_phones = dynamodb.Table('phones')
            put_record_phones(table_phones, owner_phone)

            link = "http://smart-door-b2.s3.amazonaws.com/index.html?bucket={}&filename={}".format(bucket_name, filename)
            send_message(owner_phone, link)

        else:
            # There is a match

            faceId = rek['FaceSearchResponse'][0]['MatchedFaces'][0]['Face']['FaceId']

            # Look up from database
            response_visitors = get_database('visitors', 'faceId', faceId)
            phone = response_visitors['Item']['phone']['S']

            # Spam control
            if spam_control(phone):
                return {
                    'statusCode': 200,
                    'body': json.dumps('Spam control activated')
                }

            otp = OTP()

            # Put item in database
            table_passcodes = dynamodb.Table('passcodes')
            put_record_passcodes(table_passcodes, faceId, otp)

            # Put phone in database
            table_phones = dynamodb.Table('phones')
            put_record_phones(table_phones, phone)


            # Send text message with OTP and link
            text_message = "OTP: {}\n\n".format(otp)
            text_message += "http://smart-door-b3.s3.amazonaws.com/index.html"
            send_message(phone, text_message)

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
