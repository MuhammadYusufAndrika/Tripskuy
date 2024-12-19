from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from fastapi.responses import JSONResponse
import ast

# Load dataset
df = pd.read_csv("https://raw.githubusercontent.com/MuhammadYusufAndrika/tripskuy-capstone/refs/heads/main/mergefixfile.csv")

# Encode categories and cities
le_category = LabelEncoder()
le_city = LabelEncoder()
df['category_encoded'] = le_category.fit_transform(df['name_category'])
df['city_encoded'] = le_city.fit_transform(df['name_city'])

# Prepare features (X) and target (y)
X = df[['category_encoded', 'price_place', 'city_encoded']]
y = df['rating_place']

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Standardize the features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Convert to tensor
X_train_tf = tf.convert_to_tensor(X_train_scaled, dtype=tf.float32)
y_train_tf = tf.convert_to_tensor(y_train.values, dtype=tf.float32)
X_test_tf = tf.convert_to_tensor(X_test_scaled, dtype=tf.float32)
y_test_tf = tf.convert_to_tensor(y_test.values, dtype=tf.float32)

# Load the model
model = tf.keras.models.load_model('tourism_model.keras')

# Create FastAPI app
app = FastAPI()

# Function to get recommendations
def get_recommendations(category, city, ticket_price):
    # Encode the inputs
    try:
        category_encoded = le_category.transform([category])[0]
        city_encoded = le_city.transform([city])[0]
    except ValueError:
        return {"error": "Invalid category or city."}
    
    # Standardize the input
    input_data = scaler.transform([[category_encoded, ticket_price, city_encoded]])
    input_tensor = tf.convert_to_tensor(input_data, dtype=tf.float32)
    
    # Predict the rating
    predicted_rating = float(model.predict(input_tensor, verbose=0)[0][0])
    
    # Filter and get top recommendations
    filtered_df = df[(df['name_category'] == category) & (df['name_city'] == city)]
    
    if filtered_df.empty:
        return {"error": "No destinations match the criteria."}
    
    filtered_df['price_diff'] = abs(filtered_df['price_place'] - ticket_price)
    recommendations = filtered_df.nsmallest(10, 'price_diff')[['name_place', 'price_place', 'rating_place', 'desc_place', 'coordinate', 'url_image']]
    
    # Convert coordinate to dict format (lat, lng)
    recommendations['coordinate'] = recommendations['coordinate'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
    
    # Rename columns for the response
    recommendations = recommendations.rename(columns={
        'price_place': 'ticket_place',
    })

    return {
        "predicted_rating": predicted_rating,
        "recommendations": recommendations.to_dict(orient='records')
    }

# Define schema for POST requests
class RecommendationRequest(BaseModel):
    category: str
    city: str
    ticket_price: float

# Define API route to get recommendations using POST
@app.post("/recommendations/")
async def post_recommendations(req: RecommendationRequest):
    result = get_recommendations(req.category, req.city, req.ticket_price)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(content=result)

# Define API route to get recommendations using GET
@app.get("/recommendations/")
async def get_recommendations_route(category: str, city: str, ticket_price: float):
    result = get_recommendations(category, city, ticket_price)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(content=result)

# To run the FastAPI app, use the command:
# uvicorn <filename>:app --reload
