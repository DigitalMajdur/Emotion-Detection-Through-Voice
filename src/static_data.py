#The following code can classify emotions with 93-95% accuracy. The code is for static data i.e. audio files you may already have in audio format .wav
#The code can sometimes mismatch neutral/calm/sad as the tone and pitch is in very similar range for this emotions

#Code:

import os
import librosa
import numpy as np
import pandas as pd
from tqdm import tqdm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils import class_weight
import seaborn as sns
import matplotlib.pyplot as plt
from tensorflow.keras import models  
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.regularizers import l2
import pickle
import sounddevice as sd

#extract features from audio

def extract_features(file_path):
    """Extract MFCC, Chroma, and Spectral Contrast features from an audio file."""
    try:
        audio, sr = librosa.load(file_path, sr=16000) 
        if len(audio) == 0:
            raise ValueError("Audio file is empty")
            
        mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        chroma = librosa.feature.chroma_stft(y=audio, sr=sr)
        contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)

        features = np.hstack([ 
            np.mean(mfccs, axis=1),
            np.std(mfccs, axis=1),
            np.mean(chroma, axis=1),
            np.mean(contrast, axis=1)
        ])
        return features
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return None

#dataset path
data_path = r"C:\Users\Kamlesh\Downloads\ravdess"
files = [] 

for root, dirs, filenames in os.walk(data_path):
    for filename in filenames:
        if filename.endswith('.wav'):
            files.append(os.path.join(root, filename))

print(f"Found {len(files)} audio files.")

labels = {
    '01': 'neutral', '02': 'calm', '03': 'happy', '04': 'sad',
    '05': 'angry', '06': 'fearful', '07': 'disgust', '08': 'surprised'
}

data = []
failed_files = []


for file_path in tqdm(files, desc="Processing audio files"):
    features = extract_features(file_path)
    if features is not None:
        parts = os.path.basename(file_path).split('-')
        emotion_code = parts[2]
        emotion_label = labels[emotion_code]
        data.append((features, emotion_label))
    else:
        failed_files.append(file_path)

if failed_files:
    print(f"Failed to process {len(failed_files)} files")

df = pd.DataFrame(data, columns=['features', 'emotion'])

X = np.array(df['features'].tolist())
y = np.array(df['emotion'].tolist())

#labeling
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)  
y_categorical = to_categorical(y_encoded)    


X_train, X_test, y_train, y_test = train_test_split(X, y_categorical, test_size=0.2, random_state=42)


scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)


with open('scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)


num_features = X_train.shape[1]
num_classes = y_categorical.shape[1]

model = Sequential([
    Input(shape=(num_features,)),
    Dense(256, activation='relu', kernel_regularizer=l2(0.01)),
    BatchNormalization(),
    Dropout(0.4),
    Dense(128, activation='relu', kernel_regularizer=l2(0.01)),
    BatchNormalization(),
    Dropout(0.4),
    Dense(64, activation='relu', kernel_regularizer=l2(0.01)),
    BatchNormalization(),
    Dropout(0.3),
    Dense(num_classes, activation='softmax')
])


model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

callbacks = [
    EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
    ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6),
    ModelCheckpoint('best_model.keras', monitor='val_accuracy', save_best_only=True)
]


class_weights = dict(zip(
    range(num_classes),
    class_weight.compute_class_weight('balanced', 
                                    classes=np.unique(y_encoded),
                                    y=y_encoded)
))

history = model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=100,
    batch_size=32,
    callbacks=callbacks,
    class_weight=class_weights
)

test_loss, test_accuracy = model.evaluate(X_test, y_test)
print(f"\nTest Accuracy: {test_accuracy:.2f}")

#prediction
y_pred = model.predict(X_test)

y_pred_classes = np.argmax(y_pred, axis=1)
y_test_classes = np.argmax(y_test, axis=1)

#classification
print("\nClassification Report:")
print(classification_report(y_test_classes, y_pred_classes, 
                          target_names=label_encoder.classes_))
#confusion matrix
plt.figure(figsize=(10, 8))
cm = confusion_matrix(y_test_classes, y_pred_classes)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=label_encoder.classes_,
            yticklabels=label_encoder.classes_)
plt.title('Confusion Matrix')
plt.ylabel('True Label')
plt.xlabel('Predicted Label')
plt.show()


plt.figure(figsize=(12, 4))
plt.subplot(1, 2, 1)
plt.plot(history.history['loss'], label='Training Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.title('Model Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(history.history['accuracy'], label='Training Accuracy')
plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
plt.title('Model Accuracy')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.legend()
plt.show()

with open('scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

test_file_path = r"c:\Users\Kamlesh\Downloads\tress\TESS Toronto emotional speech set data\YAF_disgust\YAF_thought_disgust.wav"
test_features = extract_features(test_file_path)

if test_features is not None:
    test_features_scaled = scaler.transform([test_features])  # Scaling it

    emotion_prediction = model.predict(test_features_scaled)
    
    predicted_class = np.argmax(emotion_prediction, axis=1)
    predicted_emotion = label_encoder.inverse_transform(predicted_class)
    
    print(f"Predicted emotion: {predicted_emotion[0]}")
else:
    print("Error processing the audio file.")