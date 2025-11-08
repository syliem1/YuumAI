
import joblib
import os
import json
import numpy as np

def model_fn(model_dir):
    '''Loads the model'''
    model_path = os.path.join(model_dir, 'playstyle_profiler.pkl')
    model_artifacts = joblib.load(model_path)
    return model_artifacts

def input_fn(request_body, content_type='application/json'):
    '''Deserializes input data'''
    if content_type == 'application/json':
        data = json.loads(request_body)
        return data
    raise ValueError(f'Unsupported content type: {content_type}')

def predict_fn(input_data, model_artifacts):
    '''Makes predictions'''
    scaler = model_artifacts['scaler']
    kmeans = model_artifacts['kmeans']
    pca = model_artifacts['pca']
    archetype_names = model_artifacts['archetype_names']
    
    # Extract features
    features = input_data['features']
    X = np.array(features).reshape(1, -1)
    
    # Transform and predict
    X_scaled = scaler.transform(X)
    X_pca = pca.transform(X_scaled)
    cluster = kmeans.predict(X_pca)[0]
    
    return {
        'cluster': int(cluster),
        'archetype': archetype_names[cluster]['name'],
        'profile': archetype_names[cluster]['profile']
    }

def output_fn(prediction, accept='application/json'):
    '''Serializes predictions'''
    if accept == 'application/json':
        return json.dumps(prediction), accept
    raise ValueError(f'Unsupported accept type: {accept}')
