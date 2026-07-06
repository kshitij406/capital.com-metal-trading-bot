Capital.com logo
Search...
General information
Getting started
Available functionality
Examples and collections
Changelog
Authentication
Symbology
Orders and positions
FAQ
WebSocket API
MCP
REST API
General
Session
Accounts
Trading
Trading > Рositions
Trading > Orders
Markets Info > Markets
Markets Info > Prices
Markets Info > Client Sentiment
Watchlists
redocly logoAPI docs by Redocly
Capital.com Public API (1.0.0)
The Capital.com API allows direct access to the latest version of our trading engine.

General information
Base URL: https://api-capital.backend-capital.com/
Base demo URL: https://demo-api-capital.backend-capital.com/
In order to use the endpoints a session should be launched. This can be done using the POST ​​/session endpoint.
Session is active for 10 minutes. In case your inactivity is longer than this period then an error will occur upon next request.
The API covers the full range of available instruments, licences and trading functionality.
Getting started
To use the API the following simple steps should be taken:

Create a trading account
Note that a demo account can be used.
Turn on Two-Factor Authentication (2FA)
2FA should be turned on prior to API key generation. Instruction for 2FA enabling.
Generate an API key
To generate the API key, go to Settings > API integrations > Generate new key. There you will need to enter the label of the key, set the custom password for it and an optional expiration date, enter the 2FA code and that’s it.
You are all set!
Available functionality
Market data
Receive real-time prices for the whole range of available assets with the REST and WebSocket API.
Get the price history for the whole range of assets.
Trading functionality
Open positions, set stop and limit orders, set stop loss and take profit levels.
Review and change financial account settings (trading modes, leverage sizes).
Review trades and orders history.
Examples and collections
Postman collection: https://github.com/capital-com-sv/capital-api-postman
Trading bot based on the RSI indicator values: https://github.com/capital-com-sv/api-java-samples
Changelog
November 28, 2023
Added an opportunity to adjust the balance of the Demo account using the POST /accounts/topUp endpoint
October 05, 2023
Limit of 1 request per second is set for the POST /session endpoint.
August 04, 2023
Added an opportunity to view the whole list of available markets using the GET /markets endpoint
July 04, 2023
Set maximum date range for parameters from, to, lastPeriod to 1 day for the GET /history/activity
March 23, 2022
Limit of 1000 requests per hour is set for the POST /positions and POST /workingorders in Demo.
March 16, 2022
WebSocket API endpoints added to Swagger documentation.
February 10, 2022
Release of the first version of the REST and WebSocket API.
Authentication
How to start new session?
There are 2 ways to start the session:

Using your API key, login and password details.
Using your API key, login and encrypted password details.
Using your API key, login and password details
Here you should simply use the POST /session endpoint and mention the received in the platform’s Settings API key in the X-CAP-API-KEY header, login and API key password info in the identifier and password parameters. The value of the encryptedPassword parameter should be false.

Using your API key, login and encrypted password details
First of all you should use the GET ​/session​/encryptionKey and mention the generated in the platform’s Settings API key in the X-CAP-API-KEY header. As a response you will receive the encryptionKey and timeStamp parameters;
Using the received encryptionKey and timeStamp parameters you should encrypt your API key password using the AES encryption method.
Encryption request example:

public static String encryptPassword(String encryptionKey, Long timestamp, String password) {
    try {
        byte[] input = stringToBytes(password + "|" + timestamp);
        input = Base64.encodeBase64(input);
        KeyFactory keyFactory = KeyFactory.getInstance(RSA_ALGORITHM);
        PublicKey publicKey = keyFactory.generatePublic(new X509EncodedKeySpec(Base64.decodeBase64(stringToBytes(encryptionKey))));
        Cipher cipher = Cipher.getInstance(PKCS1_PADDING_TRANSFORMATION);
        cipher.init(Cipher.ENCRYPT_MODE, publicKey);
        byte[] output = cipher.doFinal(input);
        output = Base64.encodeBase64(output);
        return bytesToString(output);
    } catch (Exception e) {
        throw new RuntimeException(e);
    }
}
Encrypted password example:

encryptionKey = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1dOujgcFh/9n4JLJMY4VMWZ7aRrynwKXUC9RuoC8Qu5UOeskxgZ1q5DmAXjkes77KrLfFZYEKtrp2g1TB0MBkSALiyrG+Fl52vhET9/AWRhvHuFyskWI7tEtcGIaOB1FwR0EDO9bnylTaZ+Y9sPbLVA7loAtfaX3HW/TI9JDpdmgzXZ0KrwIxdMRzPxVqQXcA8yJL1m33pvo9mOJ0AsQ8FFuy+ctjI8l/8xUhe2Hk01rpMBXDwI1lSjnvuUUDvAtacxyYVlNsnRvbrMZYp7hyimm27RtvCUXhTX2A94tDB0MFLApURrki+tvTvw5ImDPN8qOdTUzbs8hNtVwTpSxPwIDAQAB";
timestamp = 1647440528194;
password = "1111qqqq";
// Result of password encryption with the encryptionKey
encryptedPassword = "hUxWlqKRhH6thdjJnR7DvdlGE7ABkcKHrzKDGeE7kQ7nKg91sw7BpYsLDqtxihnlHN2IEmFPZ/ZmOKBAwEAw9/vjELmAZDeKsu3Q6s+Koj4wt8giE1Sxv76JjjOB/667dEeL22IFO1rwTMZ1NS5DrfeYbTfOdQgA0v5eIOS3fH8Pp/mFHodibY28X+zIaNwk6Rcb49l6aiXwM1CAtDl359qK633a+sEB9TR0/C3EaRkuGg8wAQyQ0JERaSYOZ58Dx7pw//cmvk/U5dkQlgli2l6Ts2cMhqYXCD1ZlTDA/rLfl52lgnarfari3n0uh6LicmNeWXJBF5oxj3LCruVwMA==";
Go to the POST ​/session endpoint, set true value for the encryptedPassword parameter and mention the received in the platform’s Settings API key in the X-CAP-API-KEY header, login and prior encrypted API key password info in the identifier and password parameters
After starting the session
On starting the session you will receive the CST and X-SECURITY-TOKEN parameters in the response headers. CST is an authorization token, X-SECURITY-TOKEN shows which financial account is used for the trades. These headers should be passed on subsequent requests to the API. Both tokens are valid for 10 minutes after the last use.

Symbology
Financial accounts
accountId is the ID of your financial account. Each financial account has its unique ID. To view the full list of the available financial accounts, use the GET ​​/accounts endpoint. To find out which financial account is used for trading operations in the API please go to the GET ​/session endpoint. To change the financial account use: PUT ​/session.
Epic
Epic is the name of the market pair. You can use the GET /markets{?searchTerm} endpoint to find the market pairs you are interested in. A simple market name like ‘Bitcoin’ or ‘BTC’ can be requested with the searchTerm parameter and you will receive the full list of the market pairs associated with it. The GET ​/marketnavigation endpoint can be used to obtain asset group names. These names can be used with the GET ​​/marketnavigation​/{nodeId} endpoint to view the list of assets under the corresponding group.
Watchlists
The Watchlist is the list of assets which can be seen and created on the platform. The GET /watchlists endpoint returns the existing watchlists on your account. Each watchlist has an id parameter which can be used to obtain the corresponding list of assets: GET ​/watchlists​/{watchlistId}
Orders and positions
When opening a position using the POST /positions endpoint a dealReference parameter is included in the response. However, a successful response does not always mean that the position has been successfully opened. The status of the position can be confirmed using GET ​/confirms​/{dealReference}. This will produce the status of the position together with the affectedDeals array. Note that several positions can be opened at a time: this info will be shown in the affectedDeals array.
It is important to ensure that the correct trading mode is in use with the API. To find out which trading mode is set on your financial account use the GET ​/accounts​/preferences method. The hedgingMode parameter value shows whether the hedging mode is engaged. This value can be altered using endpoint: PUT ​/accounts​/preferences.
The leverages set for trades can be obtained using the GET ​​/accounts​/preferences endpoint. To change leverages, use PUT ​​/accounts​/preferences.
Note: Stop loss and take profit values cannot be set when conducting trades with real stocks.
FAQ
Which kind of APIs do you have?
On Capital.com we suggest both REST and WebSocket API. In case of WebSocket API real-time prices updates for max 40 instruments at a time.

Do you have any limitations on your API?
Yes, we do have several limitations in our Capital.com API. Here is the list:

You have max 100 attempts per 24hrs to successfully generate API keys.
The maximum request rate is 10 per second per user.
The maximum request rate is 1 per 0.1 seconds per user when opening positions or creating orders. Otherwise the position/order requests are going to be rejected.
WebSocket session duration is 10 minutes. In order to keep the session live use the ping endpoint.
REST session is also active for 10 minutes. In case your inactivity is longer than this period then an error will occur upon next request.
POST /session endpoint limit is 1 request per second per API key.
POST /positions and POST /workingorders endpoint limit is 1000 requests per hour in the Demo account.
POST /accounts/topUp endpoint limits: 10 requests per second and 100 requests per account per day.
The balance of the Demo account cannot exceed 100000.
The WebSocket API allows subscription to a maximum of 40 instruments.
WebSocket streaming falls off when the financial account is changed with the help of the PUT​ /session endpoint.
Does your API support all the instruments?
Yes, Capital.com API supports all of the instruments which you can find on the platform.

How to start using Capital.com API?
In order to start using our Capital.com API you should first of all generate an API key in the Settings > API integrations section on the platform. Upon doing so you will be able to use this key and your account credentials to authorise for the API usage with the POST /session method.

Can I use Capital.com API on the Demo account?
Sure. In order to use your Demo account with our API you should mention the following service as Base URL: https://demo-api-capital.backend-capital.com/

How to generate an API key?
In order to generate an API Key you should log in to your account, go to the Settings > API integrations section and click on the Generate API key button.

In case your 2FA is turned off you will be asked to switch on this function to ensure safe and secure keys usage.

Next you will be presented with the Generate new key window where you will be able to name your API Key, add an API key password and set an expiration date (if needed). By default the validity of the API key is 1 year.

After that you should enter your 2FA code and wait for an API Key to be generated. Once an API Key is generated you will see an API Key itself. Please, make sure to save this data as it is shown only once.

Congratulations. You should have successfully managed to integrate our API functionality. In case you have any questions - feel free to contact us (support@capital.com). We will be glad to help you.

Which kind of API Key privileges can I have?
Currently we have only 1 type of the API Keys privileges which allows trading. No Read Only API Keys can be generated.

What does a Custom password field mean during the API key generation process?
A Custom password field allows you to generate a separate password for your API key. You should use this Custom password for the API key in order to start the session.

How can I pause or launch an API key?
In order to pause or launch an API key you can click on the Pause or Play icons next to the API key in the Settings > API integrations section. This functionality allows you to either disable or enable a key when you need to do it without deleting a key itself and re-generating a new one.

How can I view more information about the API key?
In order to view more information about the API key you have generated please click on an Eye icon next to the key in the Settings > API integrations section.

I don't see my API Key. What could have happened?
There are 2 reasons for your API Key to be deleted:

your account status has changed to either SUSPENDED or BLOCKED;
your API Key has reached an expiration date.
In all other cases your API Keys should work as expected.

I see "****" instead of my API Key. How can I find a full API Key information?
According to the existing procedure the only moment you can see your API Key is during its creation. After that it will always be masked.

In case you have lost your API Key or didn't record it, you will have to create a new one and make sure that you store a new key in a secure place.

WebSocket API
In order to start using WebSocket connect to wss://api-streaming-capital.backend-capital.com/connect.

In order to keep the connection alive, ping service at least once every 10 minutes.

More information regarding the WebSocket API requests and responses parameters can be found in the table below:

Parameter	Description
destination	The subscription destination which performs as an analogue for the request endpoint in the REST API model.
correlationId	Is set to understand for which request the message was received. Helps to track the correlation between the subscription destination and response.
cst	Access token identifying the client. Can be received upon starting the session.
Is equal to CST parameter.
securityToken	Account token or account id identifying the client's current account. Can be received upon starting the session.
Is equal to X-SECURITY-TOKEN parameter.
payload	An object which contains the data regarding the corresponding markets.
Subscribe to market data
Destination: marketData.subscribe

Subscribe to the price updates by mentioning the epics
The maximum number of epics: 40

Request message example:

{
    "destination": "marketData.subscribe",
    "correlationId": "1",
    "cst": "zvkT26****nsHKk",
    "securityToken": "g6K90****QKvCS7",
    "payload": {
        "epics": [
            "OIL_CRUDE"
        ]
    }
}
Example of the response message about successful subscription:

{
    "status": "OK",
    "destination": "marketData.subscribe",
    "correlationId": "1",
    "payload": {
        "subscriptions": {
            "OIL_CRUDE": "PROCESSED"
        }
    }
}
Example of the response message with market data updates:

{
    "status": "OK",
    "destination": "quote",
    "payload": {
        "epic": "OIL_CRUDE",
        "product": "CFD",
        "bid": 93.87,
        "bidQty": 4976.0,
        "ofr": 93.9,
        "ofrQty": 5000.0,
        "timestamp": 1660297190627
    }
}
Unsubscribe from market data
Destination: marketData.unsubscribe

Unsubscribe from the prices updates

Request message example:

{
    "destination": "marketData.unsubscribe",
    "correlationId": "2",
    "cst": "zvkT26****nsHKk",
    "securityToken": "g6K90****QKvCS7",
    "payload": {
        "epics": [
            "OIL_CRUDE"
        ]
    }
}
Example of the response message about successful unsubscription:

{
    "status": "OK",
    "destination": "marketData.unsubscribe",
    "correlationId": "2",
    "payload": {
        "subscriptions": {
            "OIL_CRUDE": "PROCESSED"
        }
    }
}
Subscribe to OHLC market data
Destination: OHLCMarketData.subscribe

Subscribe to the candlestick bars updates by mentioning the epics, resolutions and bar type

List of request payload parameters:

Parameter	Format	Required?	Description
epics	string[]	YES	The list of instruments epics

Notes:
- Max number of epics is limited to 40
resolutions	string[]	NO	The list of resolutions of requested prices

Notes:
- Default value: MINUTE
- Possible values: MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK
type	string	NO	Type of candlesticks

Notes:
- Default value: classic
- Possible values: classic, heikin-ashi
Request message example:

{
    "destination": "OHLCMarketData.subscribe",
    "correlationId": "3",
    "cst": "zvkT26****nsHKk",
    "securityToken": "g6K90****QKvCS7",
    "payload": {
        "epics": [
            "OIL_CRUDE",
            "AAPL"
        ],
        "resolutions": [
            "MINUTE_5"
        ],
        "type": "classic"
    }
}
Example of the response message about successful subscription:

{
    "status": "OK",
    "destination": "OHLCMarketData.subscribe",
    "correlationId": "3",
    "payload": {
        "subscriptions": {
            "OIL_CRUDE:MINUTE_5:classic": "PROCESSED",
            "AAPL:MINUTE_5:classic": "PROCESSED"
        }
    }
}
Example of the response message with market data updates:

{
    "status": "OK",
    "destination": "ohlc.event",
    "payload": {
        "resolution": "MINUTE_5",
        "epic": "AAPL",
        "type": "classic",
        "priceType": "bid",
        "t": 1671714000000,
        "h": 134.95,
        "l": 134.85,
        "o": 134.86,
        "c": 134.88
    }
}
Unsubscribe from OHLC market data
Destination: OHLCMarketData.unsubscribe

Unsubscribe from candlestick bars updates for specific epics, resolutions and bar types.

The general principle is as follows: you unsubscribe from the parameter you mention in the request. In case you mention epic you unsubscribe from all of the corresponding bar types and resolutions.

List of request payload parameters:

Parameter	Format	Required?	Description
epics	string[]	YES	The list of instruments epics to be unsubscribed
resolutions	string[]	NO	The list of price resolutions to be unsubscribed

Notes:
- Default value: All possible values
- Possible values: MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK
types	string[]	NO	Types of candlesticks to be unsubscribed

Notes:
- Default value: all possible values
- Possible values: classic, heikin-ashi
Request message example:

// Unsubscribe from candlestick bars updates of OIL_CRUDE epic with MINUTE and MINUTE_5 resolutions and heikin-ashi candlestick type
{
    "destination": "OHLCMarketData.unsubscribe",
    "correlationId": "4",
    "cst": "zvkT26****nsHKk",
    "securityToken": "g6K90****QKvCS7",
    "payload": {
        "epics": [
            "OIL_CRUDE"
        ],
        "resolutions": [
            "MINUTE",
            "MINUTE_5"
        ],
        "types": [
            "heikin-ashi"
        ]
    }
}
Example of the response message about successful unsubscription:

{
    "status": "OK",
    "destination": "OHLCMarketData.unsubscribe",
    "correlationId": "4",
    "payload": {
        "subscriptions": {
            "OIL_CRUDE:MINUTE_5:heikin-ashi": "PROCESSED",
            "OIL_CRUDE:MINUTE:heikin-ashi": "PROCESSED"
        }
    }
}
Ping the service
Destination: ping

Ping the service for keeping the connection alive

Request message example:

{
    "destination": "ping",
    "correlationId": "5",
    "cst": "zvkT26****nsHKk",
    "securityToken": "g6K90****QKvCS7"
}
Response message example:

{
    "status": "OK",
    "destination": "ping",
    "correlationId": "5",
    "payload": {}
}
MCP
The Capital.com MCP (Model Context Protocol) server enables AI assistants to interact with your Capital.com trading account — retrieve market data, manage positions, and execute trades through natural language. Trading is disabled by default and requires explicit configuration; always start with a Demo account.

Full installation and configuration guide: README.

Important Notice
Your use of the Capital.com Public API and any third-party tools you connect to it, including AI or LLM-based tools, is at your own discretion and risk. Capital.com operates on an execution-only basis and does not control, endorse, or accept liability for any third-party software, its outputs, or any resulting outcomes. Nothing on this page constitutes investment advice or a recommendation to trade. You are solely responsible for all trading decisions, configurations, and automated activity on your account, and must ensure your use complies with Capital.com 's Terms and Conditions, Electronic Trading Terms, and all applicable laws in your jurisdiction.

Crypto Derivatives are not available to Retail clients registered with Capital Com (UK) Ltd.

Always start with a Demo account before considering live trading

Trading is disabled by default and requires explicit configuration

All trade operations require two-phase execution (preview → confirm → execute)

Built-in risk controls: allowlists, size limits, daily order caps

Use at your own risk - the authors assume no liability for trading losses

For further questions/clarifications, please refer to the FAQ: https://help.capitalccuk.com/hc/en-us/articles/34503231743506-How-to-set-up-the-Capital-com-MCP-Server

REST API
Find below the list of all available REST API endpoints

General
Get server time
Test connectivity to the API and get the current server time

Authentication is not required for this endpoint

Responses
200 OK

get
/api/v1/time


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/time", Method.Get);
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
{
"serverTime": 1649259764171
}
Ping the service
Ping the service to keep a trading session alive

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token or account id identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/ping


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/ping", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
{
"status": "OK"
}
Session
Encryption key
Get the encryption key to use in order to send the API key password in an encrypted form

header Parameters
X-CAP-API-KEY	
string
Example: ENTER_GENERATED_API_KEY
The API key obtained from Settings > API Integrations page on the Capital.com trading platform

Responses
200 OK

get
/api/v1/session/encryptionKey


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/session/encryptionKey", Method.Get);
request.AddHeader("X-CAP-API-KEY", "ENTER_GENERATED_API_KEY");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
{
"encryptionKey": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxOZgr4OMjNBMKpR+fZpxrDGGwDk3eGnrI+AvRq1X+psNZEjcQ/tR7XkXfy/BzhXKsrdJO4dqwFrULg03olkhapNpo0wr3Jhr3QLPOeX7bAvgL1pkg/1/ySX4ZPZ8tYuGFXRX0v/DeMYJFFiW1NjHS2phTlmVAHy6a5VRx/GmkvBxo/Xh6L0uaIZIbxNRoU1T+4oR7eaIVKtDL5uxX518EgvpU5QNFMg03Z+e5BTczCPR7xmnpKFMsu40zdICtdylxHXBupuh9zeQ5Rbx1xc72x3emUxL4PRCTh/t0gb9mCID4/AIQqSRykY9NpfkXGJV5mBN/3ZHJanHiE2mnVTlbwIBOOBA",
"timeStamp": 1649058606014
}
Session details
Returns the user's session details

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token or account id identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/session


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/session", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
{
"clientId": "12345678",
"accountId": "12345678901234567",
"timezoneOffset": 3,
"locale": "en",
"currency": "USD",
"streamEndpoint": "wss://api-streaming-capital.backend-capital.com/"
}
Create new session
Create a trading session, obtaining session tokens for subsequent API access

Session is active for 10 minutes. In case your inactivity is longer than this period then you need to create a new session

Endpoint limit: 1 request per second

List of request body parameters:

Parameter	Format	Required?	Description
identifier	string	YES	Client login identifier
password	string	YES	API key custom password
encryptedPassword	boolean	NO	Whether the password has been encrypted.
Default value: false
header Parameters
X-CAP-API-KEY	
string
Example: ENTER_GENERATED_API_KEY
The API key obtained from Settings > API Integrations page on the Capital.com trading platform

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request
401 Unauthorized
429 Too Many Requests

post
/api/v1/session


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"identifier": "ENTER_YOUR_EMAIL",
"password": "ENTER_YOUR_PASSWORD"
}
Response samples
200400401429
Content type
text/plain
Example

Success: Session created (basic password)
Success: Session created (basic password)

Copy
{
	"accountType": "CFD",
	"accountInfo": {
        "balance": 92.89,
        "deposit": 90.38,
        "profitLoss": 2.51,
        "available": 64.66
    },
	"currencyIsoCode": "USD",
	"currencySymbol": "$",
	"currentAccountId": "12345678901234567",
	"streamingHost": "wss://api-streaming-capital.backend-capital.com/",
	"accounts": [
        {
            "accountId": "12345678901234567",
            "accountName": "USD",
            "preferred": true,
            "accountType": "CFD",
            "currency": "USD",
            "symbol": "$",
            "balance": {
                "balance": 92.89,
                "deposit": 90.38,
                "profitLoss": 2.51,
                "available": 64.66
            }
        },
        {
            "accountId": "12345678907654321",
            "accountName": "EUR",
            "preferred": false,
            "accountType": "CFD",
            "currency": "EUR",
            "symbol": "€",
            "balance": {
                "balance": 0.0,
                "deposit": 0.0,
                "profitLoss": 0.0,
                "available": 0.0
            }
        }
	],
	"clientId": "12345678",
	"timezoneOffset": 3,
	"hasActiveDemoAccounts": true,
	"hasActiveLiveAccounts": true,
	"trailingStopsEnabled": false
}
Switches active account
Switch active account

List of request body parameters:

Parameter	Format	Required?	Description
accountId	string	YES	The identifier of the account being switched to
header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request

put
/api/v1/session


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"accountId": "12345678907654321"
}
Response samples
200400
Content type
application/json

Copy
{
"trailingStopsEnabled": false,
"dealingEnabled": true,
"hasActiveDemoAccounts": false,
"hasActiveLiveAccounts": true
}
Log out of the current session
Log out of the current session

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

delete
/api/v1/session


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/session", Method.Delete);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
text/plain

Copy
{
    "status": "SUCCESS"
}
Accounts
All accounts
Returns a list of accounts belonging to the logged-in client

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/accounts


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/accounts", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
Expand allCollapse all
{
"accounts": [
{},
{}
]
}
Account preferences
Returns account preferences, i.e. leverage settings and trading mode

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/accounts/preferences


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/accounts/preferences", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
Expand allCollapse all
{
"hedgingMode": false,
"leverages": {
"SHARES": {},
"CURRENCIES": {},
"INDICES": {},
"CRYPTOCURRENCIES": {},
"COMMODITIES": {}
}
}
Update account preferences
Update account preferences

List of request body parameters:

Parameter	Format	Required?	Description
leverages	object	NO	Set new leverage values
hedgingMode	boolean	NO	Enable or disable hedging mode
header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request

put
/api/v1/accounts/preferences


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
Expand allCollapse all
{
"leverages": {
"SHARES": 5,
"CURRENCIES": 10,
"INDICES": 20,
"CRYPTOCURRENCIES": 2,
"COMMODITIES": 5
},
"hedgingMode": false
}
Response samples
200400
Content type
application/json

Copy
{
"status": "SUCCESS"
}
Account activity history
Returns the account activity history

All query parameters are optional for this request

The maximum possible date range between from and to parameters is 1 day. If only one of the parameters is specified (from or to), the 1-day date range will be selected by default

Possible enum values for parameters in FIQL filter:

Parameter	ENUM
source	CLOSE_OUT, DEALER, SL, SYSTEM, TP, USER
status	ACCEPTED, CREATED, EXECUTED, EXPIRED, REJECTED, MODIFIED, MODIFY_REJECT, CANCELLED, CANCEL_REJECT, UNKNOWN
type	POSITION, WORKING_ORDER, EDIT_STOP_AND_LIMIT, SWAP, SYSTEM
query Parameters
from	
string
Example: from=2022-01-17T15:09:47
Start date. Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-04-01T01:01:00). Filtration by date based on dateUTC parameter

to	
string
Example: to=2022-01-17T15:10:05
End date. Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-04-01T01:01:00). Filtration by date based on dateUTC parameter

lastPeriod	
integer
Example: lastPeriod=600
Limits the timespan in seconds through to current time (not applicable if a date range has been specified). Cannot be bigger than current Unix timestamp value. Default = 600, max = 86400

detailed	
boolean
Example: detailed=true
Indicates whether to retrieve additional details about the activity. False by default

dealId	
string
Example: dealId={{dealId}}
Get activity information for specific dealId

filter	
string
Example: filter=source!=DEALER;type!=POSITION;status==REJECTED;epic==OIL_CRUDE,GOLD
Filter activity list using FIQL. List of supported parameters: epic, source, status, type

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
400 Bad Request

get
/api/v1/history/activity


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/history/activity?from=2022-01-17T15:09:47&to=2022-01-17T15:10:05&lastPeriod=600&detailed=true&dealId={{dealId}}&filter=source!=DEALER;type!=POSITION;status==REJECTED;epic==OIL_CRUDE,GOLD", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200400
Content type
application/json
Example

Success: Filter list by date
Success: Filter list by date

Copy
Expand allCollapse all
{
"activities": [
{},
{},
{}
]
}
Account transactions history
Returns the transaction history. By default returns the transactions within the last 10 minutes

All query parameters are optional for this request

query Parameters
from	
string
Example: from=2021-08-10T00:00:00
Start date. Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-04-01T01:01:00). Filtration by date based on dateUTC parameter

to	
string
Example: to=2021-09-10T00:00:01
End date. Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-04-01T01:01:00). Filtration by date based on dateUTC parameter

lastPeriod	
integer
Example: lastPeriod=600
Limits the timespan in seconds through to current time (not applicable if a date range has been specified). Cannot be bigger than current Unix timestamp value. Default = 600

type	
string
Example: type=DEPOSIT
Transaction type. Possible values: INACTIVITY_FEE, RESERVE, VOID, UNRESERVE, WRITE_OFF_OR_CREDIT, CREDIT_FACILITY, FX_COMMISSION, COMPLAINT_SETTLEMENT, DEPOSIT, WITHDRAWAL, REFUND, WITHDRAWAL_MONEY_BACK, TRADE, SWAP, TRADE_COMMISSION, TRADE_COMMISSION_GSL, NEGATIVE_BALANCE_PROTECTION, TRADE_CORRECTION, CHARGEBACK, ADJUSTMENT, BONUS, TRANSFER, CORPORATE_ACTION, CONVERSION, REBATE, TRADE_SLIPPAGE_PROTECTION

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/history/transactions


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/history/transactions?from=2021-08-10T00:00:00&to=2021-09-10T00:00:01&lastPeriod=600&type=DEPOSIT", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json
Example

Success: Get list of transactions within last hour
Success: Get list of transactions within last hour

Copy
Expand allCollapse all
{
"transactions": [
{},
{}
]
}
Adjust balance of Demo account
Adjust the balance of the current Demo account.

Note: The balance of the Demo account cannot exceed 100000.

Limits:

10 requests per second;
100 requests per account per day.
List of request body parameters:

Parameter	Format	Required?	Description
amount	number	YES	The amount of funds that will be added to the Demo account balance

Notes:
- Min value = -400000
- Max value = 400000
header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request

post
/api/v1/accounts/topUp


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"amount": 1000
}
Response samples
200400
Content type
application/json

Copy
{
"successful": true
}
Trading
Position/Order confirmation
Returns a deal confirmation for the given deal reference

In case of mentioning the order prefix formed because of the position creation the opened positions IDs will be shown in the affectedDeals array

path Parameters
dealReference
required
string
Example: {{dealReference}}
Deal reference for an unconfirmed trade

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

get
/api/v1/confirms/{dealReference}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/confirms/{{dealReference}}", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
Expand allCollapse all
{
"date": "2022-04-06T07:32:19.193",
"status": "OPEN",
"dealStatus": "ACCEPTED",
"epic": "SILVER",
"dealReference": "o_fcc7e6c0-c150-48aa-bf66-d6c6da071f1a",
"dealId": "006011e7-0001-54c4-0000-000080560043",
"affectedDeals": [
{}
],
"level": 24.285,
"size": 1,
"direction": "BUY",
"guaranteedStop": false,
"trailingStop": false
}
Trading > Рositions
All positions
Returns all open positions for the active account

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/positions


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/positions", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
Expand allCollapse all
{
"positions": [
{},
{}
]
}
Create position
Create orders and positions

Please note that when creating the position an order is created first with the 'o_' prefix in the dealReference parameter

List of request body parameters:

Parameter	Format	Required?	Description
direction	string	YES	Deal direction

Must be BUY or SELL
epic	string	YES	Instrument epic identifier
size	number	YES	Deal size
guaranteedStop	boolean	NO	Must be true if a guaranteed stop is required

Notes:
- Default value: false
- If guaranteedStop equals true, then set stopLevel, stopDistance or stopAmount
- Cannot be set if trailingStop is true
- Cannot be set if hedgingMode is true
trailingStop	boolean	NO	Must be true if a trailing stop is required

Notes:
- Default value: false
- If trailingStop equals true, then set stopDistance
- Cannot be set if guaranteedStop is true
stopLevel	number	NO	Price level when a stop loss will be triggered
stopDistance	number	NO	Distance between current and stop loss triggering price

Notes:
- Required parameter if trailingStop is true
stopAmount	number	NO	Loss amount when a stop loss will be triggered
profitLevel	number	NO	Price level when a take profit will be triggered
profitDistance	number	NO	Distance between current and take profit triggering price
profitAmount	number	NO	Profit amount when a take profit will be triggered
header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request

post
/api/v1/positions


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"epic": "SILVER",
"direction": "BUY",
"size": 1,
"guaranteedStop": true,
"stopLevel": 20,
"profitLevel": 27
}
Response samples
200400
Content type
application/json
Example

Success: Create simple position
Success: Create simple position

Copy
{
"dealReference": "o_98c0de50-9cd5-4481-8d81-890c525eeb49"
}
Single position
Returns an open position for the active account by deal identifier

path Parameters
dealId
required
string
Example: {{dealId}}
Permanent deal reference for a confirmed trade

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

get
/api/v1/positions/{dealId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/positions/{{dealId}}", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
Expand allCollapse all
{
"position": {
"contractSize": 1,
"createdDate": "2022-04-06T10:49:52.056",
"createdDateUTC": "2022-04-06T07:49:52.056",
"dealId": "006011e7-0001-54c4-0000-00008056005e",
"dealReference": "p_006011e7-0001-54c4-0000-00008056005e",
"workingOrderId": "006011e7-0001-54c4-0000-00008056005c",
"size": 1,
"leverage": 20,
"upl": -0.022,
"direction": "BUY",
"level": 21.059,
"currency": "USD",
"guaranteedStop": false
},
"market": {
"instrumentName": "Silver",
"expiry": "-",
"marketStatus": "TRADEABLE",
"epic": "SILVER",
"symbol": "Natural Gas",
"instrumentType": "COMMODITIES",
"lotSize": 1,
"high": 21.167,
"low": 20.823,
"percentageChange": 1.8478,
"netChange": 0.381,
"bid": 21.037,
"offer": 21.057,
"updateTime": "2022-04-06T10:53:35.389",
"updateTimeUTC": "2022-04-06T07:53:35.389",
"delayTime": 0,
"streamingPricesAvailable": true,
"scalingFactor": 1,
"marketModes": []
}
}
Update position
Update the position

List of request body parameters:

Parameter	Format	Required?	Description
guaranteedStop	boolean	NO	Must be true if a guaranteed stop is required

Notes:
- Default value: false
- If guaranteedStop equals true, then set stopLevel, stopDistance or stopAmount
- Cannot be set if trailingStop is true
- Cannot be set if hedgingMode is true
trailingStop	boolean	NO	Must be true if a trailing stop is required

Notes:
- Default value: false
- If trailingStop equals true, then set stopDistance
- Cannot be set if guaranteedStop is true
stopLevel	number	NO	Price level when a stop loss will be triggered
stopDistance	number	NO	Distance between current and stop loss triggering price

Notes:
- Required parameter if trailingStop is true
stopAmount	number	NO	Loss amount when a stop loss will be triggered
profitLevel	number	NO	Price level when a take profit will be triggered
profitDistance	number	NO	Distance between current and take profit triggering price
profitAmount	number	NO	Profit amount when a take profit will be triggered
path Parameters
dealId
required
string
Example: {{dealId}}
Permanent deal reference for a confirmed trade

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request
404 Not Found

put
/api/v1/positions/{dealId}


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"guaranteedStop": true,
"stopDistance": 3,
"profitAmount": 2
}
Response samples
200400404
Content type
application/json

Copy
{
"dealReference": "p_006011e7-0001-54c4-0000-000080560068"
}
Close position
Close the position

path Parameters
dealId
required
string
Example: {{dealId}}
Permanent deal reference for a confirmed trade

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

delete
/api/v1/positions/{dealId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/positions/{{dealId}}", Method.Delete);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
{
"dealReference": "p_006011e7-0001-54c4-0000-000080560068"
}
Trading > Orders
All working orders
Returns all open working orders for the active account

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/workingorders


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/workingorders", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
Expand allCollapse all
{
"workingOrders": [
{},
{}
]
}
Create working order
Create a limit or stop order

List of request body parameters:

Parameter	Format	Required?	Description
direction	string	YES	Order direction

Must be BUY or SELL
epic	string	YES	Instrument epic identifier
size	number	YES	Order size
level	number	YES	Order price
type	string	YES	Order type

Must be LIMIT or STOP
goodTillDate	string	NO	Order cancellation date in UTC time

Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-06-09T01:01:00)
guaranteedStop	boolean	NO	Must be true if a guaranteed stop is required

Notes:
- Default value: false
- If guaranteedStop equals true, then set stopLevel, stopDistance or stopAmount
- Cannot be set if trailingStop is true
- Cannot be set if hedgingMode is true
trailingStop	boolean	NO	Must be true if a trailing stop is required

Notes:
- Default value: false
- If trailingStop equals true, then set stopDistance
- Cannot be set if guaranteedStop is true
stopLevel	number	NO	Price level when a stop loss will be triggered
stopDistance	number	NO	Distance between current and stop loss triggering price

Notes:
- Required parameter if trailingStop is true
stopAmount	number	NO	Loss amount when a stop loss will be triggered
profitLevel	number	NO	Price level when a take profit will be triggered
profitDistance	number	NO	Distance between current and take profit triggering price
profitAmount	number	NO	Profit amount when a take profit will be triggered
header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request

post
/api/v1/workingorders


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"epic": "SILVER",
"direction": "BUY",
"size": 1,
"level": 20,
"type": "LIMIT"
}
Response samples
200400
Content type
application/json
Example

Success: Create limit order
Success: Create limit order

Copy
{
"dealReference": "o_307bb379-6dd8-4ea7-8935-faf725f0e0a3"
}
Update working order
Update a limit or stop order

List of request body parameters:

Parameter	Format	Required?	Description
level	number	NO	Order price
goodTillDate	string	NO	Order cancellation date in UTC time

Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-06-09T01:01:00)
guaranteedStop	boolean	NO	Must be true if a guaranteed stop is required

Notes:
- Default value: false
- If guaranteedStop equals true, then set stopLevel, stopDistance or stopAmount
- Cannot be set if trailingStop is true
- Cannot be set if hedgingMode is true
trailingStop	boolean	NO	Must be true if a trailing stop is required

Notes:
- Default value: false
- If trailingStop equals true, then set stopDistance
- Cannot be set if guaranteedStop is true
stopLevel	number	NO	Price level when a stop loss will be triggered
stopDistance	number	NO	Distance between current and stop loss triggering price

Notes:
- Required parameter if trailingStop is true
stopAmount	number	NO	Loss amount when a stop loss will be triggered
profitLevel	number	NO	Price level when a take profit will be triggered
profitDistance	number	NO	Distance between current and take profit triggering price
profitAmount	number	NO	Profit amount when a take profit will be triggered
path Parameters
dealId
required
string
Example: {{dealId}}
Permanent deal reference for an order

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
404 Not Found

put
/api/v1/workingorders/{dealId}


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"goodTillDate": "2022-06-09T01:01:00",
"guaranteedStop": true,
"stopDistance": 4,
"profitDistance": 4
}
Response samples
200404
Content type
application/json

Copy
{
"dealReference": "o_56e73aad-45fe-4058-a05b-569b1a6e8ba0"
}
Delete working order
Delete a limit or stop order

path Parameters
dealId
required
string
Example: {{dealId}}
Permanent deal reference for an order

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

delete
/api/v1/workingorders/{dealId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/workingorders/{{dealId}}", Method.Delete);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
{
"dealReference": "o_38323f0c-241a-43b3-8edf-a75d2ae989a5"
}
Markets Info > Markets
All top-level market categories
Returns all top-level nodes (market categories) in the market navigation hierarchy

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/marketnavigation


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/marketnavigation", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
Expand allCollapse all
{
"nodes": [
{},
{},
{}
]
}
All category sub-nodes
Returns all sub-nodes (markets) of the given node (market category) in the market navigation hierarchy

path Parameters
nodeId
required
string
Example: {{nodeId}}
Identifier of the node to browse

query Parameters
limit	
integer
Example: limit=500
The maximum number of the markets in answer. Default = 500, max = 500

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
400 Bad Request

get
/api/v1/marketnavigation/{nodeId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/marketnavigation/{{nodeId}}?limit=500", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200400
Content type
application/json
Example

Success: List of category sub-nodes
Success: List of category sub-nodes

Copy
Expand allCollapse all
{
"nodes": [
{},
{},
{},
{},
{},
{},
{}
]
}
Markets details
Returns the details of all or specific markets

If query parameters are not specified in the request, the list of all available markets will be returned

Request can include one of the query parameters: searchTerm or epics

If both searchTerm or epics parameters are specified in the request, only searchTerm will be used (due to higher priority)

query Parameters
searchTerm	
string
Example: searchTerm=silver
The term to be used in the search. Has higher priority, than 'epics' parameter meaning that in case both searchTerm and epic are mentioned only searchTerm is taken into consideration.

epics	
string
Example: epics=SILVER,NATURALGAS
The epics of the market, separated by a comma. Max number of epics is limited to 50

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
400 Bad Request

get
/api/v1/markets


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/markets?searchTerm=silver&epics=SILVER,NATURALGAS", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200400
Content type
application/json
Example

Successful response: searchTerm
Successful response: searchTerm

Copy
Expand allCollapse all
{
"markets": [
{},
{}
]
}
Single market details
Returns the details of the given market

path Parameters
epic
required
string
Example: {{epic}}
The epic of the market

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

get
/api/v1/markets/{epic}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/markets/{{epic}}", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
Expand allCollapse all
{
"instrument": {
"epic": "SILVER",
"symbol": "Silver",
"expiry": "-",
"name": "Silver",
"lotSize": 1,
"type": "COMMODITIES",
"guaranteedStopAllowed": true,
"streamingPricesAvailable": true,
"currency": "USD",
"marginFactor": 10,
"marginFactorUnit": "PERCENTAGE",
"openingHours": {},
"overnightFee": {}
},
"dealingRules": {
"minStepDistance": {},
"minDealSize": {},
"maxDealSize": {},
"minSizeIncrement": {},
"minGuaranteedStopDistance": {},
"minStopOrProfitDistance": {},
"maxStopOrProfitDistance": {},
"marketOrderPreference": "AVAILABLE_DEFAULT_ON",
"trailingStopsPreference": "NOT_AVAILABLE"
},
"snapshot": {
"marketStatus": "TRADEABLE",
"netChange": -0.627,
"percentageChange": -0.27,
"updateTime": "2022-04-06T11:23:00.955",
"delayTime": 0,
"bid": 22.041,
"offer": 22.061,
"high": 22.098,
"low": 21.926,
"decimalPlacesFactor": 3,
"scalingFactor": 1,
"marketModes": []
}
}
Markets Info > Prices
Historical prices
Returns historical prices for a particular instrument

All query parameters are optional for this request

By default returns the minute prices within the last 10 minutes

path Parameters
epic
required
string
Example: {{epic}}
Instrument epic

query Parameters
resolution	
string
Example: resolution=MINUTE
Defines the resolution of requested prices. Possible values are MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK

max	
integer
Example: max=10
The maximum number of the values in answer. Default = 10, max = 1000

from	
string
Example: from=2022-02-24T00:00:00
Start date. Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-04-01T01:01:00). Filtration by date based on snapshotTimeUTC parameter

to	
string
Example: to=2022-02-24T01:00:00
End date. Date format: YYYY-MM-DDTHH:MM:SS (e.g. 2022-04-01T01:01:00). Filtration by date based on snapshotTimeUTC parameter

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
400 Bad Request

get
/api/v1/prices/{epic}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/prices/{{epic}}?resolution=MINUTE&max=10&from=2022-02-24T00:00:00&to=2022-02-24T01:00:00", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200400
Content type
application/json
Example

Success: Default response
Success: Default response

Copy
Expand allCollapse all
{
"prices": [
{},
{},
{},
{},
{},
{},
{},
{},
{},
{}
],
"instrumentType": "COMMODITIES"
}
Markets Info > Client Sentiment
Client sentiment for markets
Returns the client sentiment for the given market

query Parameters
marketIds	
string
Example: marketIds=SILVER,NATURALGAS
Comma separated list of market identifiers

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

get
/api/v1/clientsentiment


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/clientsentiment?marketIds=SILVER,NATURALGAS", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
Expand allCollapse all
{
"clientSentiments": [
{},
{}
]
}
Client sentiment for market
Returns the client sentiment for the given market

path Parameters
marketId
required
string
Example: {{marketId}}
Market identifier

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

get
/api/v1/clientsentiment/{marketId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/clientsentiment/{{marketId}}", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
{
"marketId": "SILVER",
"longPositionPercentage": 91.85,
"shortPositionPercentage": 8.15
}
Watchlists
All watchlists
Returns all watchlists belonging to the current user

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK

get
/api/v1/watchlists


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/watchlists", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200
Content type
application/json

Copy
Expand allCollapse all
{
"watchlists": [
{},
{}
]
}
Create watchlist
Create a watchlist

List of request body parameters:

Parameter	Format	Required?	Description
name	string	YES	Watchlist name

Min length = 1
Max length = 20
epics	array[string]	NO	List of market epics to be associated with this new watchlist
header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
400 Bad Request

post
/api/v1/watchlists


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
Expand allCollapse all
{
"epics": [
"SILVER",
"NATURALGAS"
],
"name": "Lorem"
}
Response samples
200400
Content type
application/json
Example

Success: Watchlist created
Success: Watchlist created

Copy
{
"watchlistId": "123458",
"status": "SUCCESS"
}
Single watchlist
Returns a watchlist for the given watchlist identifier

path Parameters
watchlistId
required
string
Example: {{watchlistId}}
Identifier of the watchlist

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

get
/api/v1/watchlists/{watchlistId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/watchlists/{{watchlistId}}", Method.Get);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
Expand allCollapse all
{
"markets": [
{},
{}
]
}
Add market to watchlist
Add a market to the watchlist

List of request body parameters:

Parameter	Format	Required?	Description
epic	string	YES	Instrument epic identifier
path Parameters
watchlistId
required
string
Example: {{watchlistId}}
Identifier of the watchlist

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Request Body schema: application/json
object
Responses
200 OK
404 Not Found

put
/api/v1/watchlists/{watchlistId}


Request samples
PayloadC#cURLHTTPJavaJavaScriptNodeJSPHPPython
Content type
application/json

Copy
{
"epic": "SILVER"
}
Response samples
200404
Content type
application/json

Copy
{
"status": "SUCCESS"
}
Delete watchlist
Delete the watchlist

path Parameters
watchlistId
required
string
Example: {{watchlistId}}
Identifier of the watchlist

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

delete
/api/v1/watchlists/{watchlistId}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/watchlists/{{watchlistId}}", Method.Delete);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
{
"status": "SUCCESS"
}
Remove market from watchlist
Remove a market from the watchlist

path Parameters
watchlistId
required
string
Example: {{watchlistId}}
Identifier of the watchlist

epic
required
string
Example: {{epic}}
Instrument epic identifier

header Parameters
X-SECURITY-TOKEN	
string
Example: ENTER_OBTAINED_SECURITY_TOKEN
Account token identifying the client's current account

CST	
string
Example: ENTER_OBTAINED_CST_TOKEN
Access token identifying the client

Responses
200 OK
404 Not Found

delete
/api/v1/watchlists/{watchlistId}/{epic}


Request samples
C#cURLHTTPJavaJavaScriptNodeJSPHPPython

Copy
var options = new RestClientOptions("https://api-capital.backend-capital.com")
{
  MaxTimeout = -1,
};
var client = new RestClient(options);
var request = new RestRequest("/api/v1/watchlists/{{watchlistId}}/{{epic}}", Method.Delete);
request.AddHeader("X-SECURITY-TOKEN", "ENTER_OBTAINED_SECURITY_TOKEN");
request.AddHeader("CST", "ENTER_OBTAINED_CST_TOKEN");
RestResponse response = await client.ExecuteAsync(request);
Console.WriteLine(response.Content);
Response samples
200404
Content type
application/json

Copy
{
"status": "SUCCESS"
}
