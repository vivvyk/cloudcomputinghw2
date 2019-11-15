import json
import random
import string
import boto3
import time
from decimal import *

def OTP(stringLength=6):
    """
    OTP
    Credit: https://pynative.com/python-generate-random-string/
    """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def add_faces_to_collection(bucket, photo, collection_id):
    '''
    Credit: https://docs.aws.amazon.com/rekognition/latest/dg/add-faces-to-collection-procedure.html
    '''
    client=boto3.client('rekognition')

    response=client.index_faces(CollectionId=collection_id,
                                Image={'S3Object':{'Bucket':bucket,'Name':photo}},
                                ExternalImageId=photo,
                                MaxFaces=1,
                                QualityFilter="AUTO",
                                DetectionAttributes=['ALL'])

    return response['FaceRecords'][0]['Face']['FaceId']

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

def put_record_visitors(table, faceID, name, phone):
    # Put record in database
    item = {}
    item['faceId'] = faceID
    item['name'] = name
    item['phone'] = phone
    table.put_item(
       Item=item
    )
    
def send_message(phone, text_message):
    sns_client = boto3.client('sns')
    sns_client.publish(
        PhoneNumber="+1" + phone,
        Message=text_message,
        Subject='Smartdoor Secure (Knock Knock)'
    )

def lambda_handler(event, context):
    # TODO implement
    
    # User parameters
    photo_name = event["photo"]
    bucket_name = event["bucket"]
    person_name = event["name"]
    phone = event["phone"]
    
    # Index image in collection
    collection_id = "smartcol"
    faceID = add_faces_to_collection(bucket_name, photo_name, collection_id)
    
    otp = OTP()
    
    # Send SNS
    text_message = "OTP: {}\n\n".format(otp)
    text_message += "http://smart-door-b3.s3.amazonaws.com/index.html"
    send_message(phone, text_message)
    
    # Insert into database
    dynamodb = boto3.resource('dynamodb')
    table_visitors = dynamodb.Table('visitors')
    table_passcodes = dynamodb.Table('passcodes') 
    put_record_passcodes(table_passcodes, faceID, otp)
    put_record_visitors(table_visitors, faceID, person_name, phone)
    
    
    return {
        'statusCode': 200,
        'body': json.dumps(faceID)
    }
