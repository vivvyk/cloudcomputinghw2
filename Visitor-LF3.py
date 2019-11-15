import json
import boto3
import time

def get_database(table, key, lookup_val):
    db_client = boto3.client('dynamodb')
    db_response = db_client.get_item(
        TableName= table,
        Key={
            key: {"S": lookup_val}
        },
    )
    return db_response

def lambda_handler(event, context):
    # TODO implement
    
    # User parameters
    OTP = event["OTP"]
    
    # Query for OTP
    response_OTP = get_database('passcodes','access-code',OTP)
    if 'Item' not in response_OTP.keys():
        return {
            'statusCode': 400,
            'body': json.dumps("Error")
        }
    
    faceId = response_OTP['Item']['faceId']['S']
    ttl = int(response_OTP['Item']['ttl']['N'])
    
    if int(time.time()) > ttl:
        return {
            'statusCode': 400,
            'body': json.dumps("Error")
        }
    
    # Query for Name and Phone
    response_visitors = get_database('visitors', 'faceId', faceId)

    name = response_visitors['Item']['name']['S']


    return {
        'statusCode': 200,
        'body': json.dumps({"name":name})
    }
        
        
