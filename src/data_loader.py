
import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Constants
IMG_HEIGHT = 48
IMG_WIDTH = 48
BATCH_SIZE = 64
TRAIN_DIR = 'data/train'
TEST_DIR = 'data/test'

def get_data_generators(train_dir=TRAIN_DIR, test_dir=TEST_DIR):
    """
    Creates and returns training and validation data generators.
    Applies data augmentation to training data to prevent overfitting.
    """
    
    # Check if directories exist
    if not os.path.exists(train_dir):
        raise FileNotFoundError(f"Training directory not found: {train_dir}")
    if not os.path.exists(test_dir):
        raise FileNotFoundError(f"Testing directory not found: {test_dir}")

    # Data Augmentation for Training (Aggressive for better generalization)
    train_datagen = ImageDataGenerator(
        rescale=1./255,             
        rotation_range=20,          # Back to 20
        width_shift_range=0.2,      # Back to 0.2
        height_shift_range=0.2,     
        shear_range=0.2,            # Back to 0.2
        zoom_range=0.2,             # Back to 0.2
        horizontal_flip=True,
        fill_mode='nearest'
    )

    # Validation Data (Only Rescaling)
    test_datagen = ImageDataGenerator(rescale=1./255)

    print(f"Loading Training Data from {train_dir}...")
    train_generator = train_datagen.flow_from_directory(
        train_dir,
        target_size=(IMG_HEIGHT, IMG_WIDTH),
        color_mode='grayscale',     # Back to Grayscale
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        shuffle=True
    )

    print(f"Loading Validation Data from {test_dir}...")
    validation_generator = test_datagen.flow_from_directory(
        test_dir,
        target_size=(IMG_HEIGHT, IMG_WIDTH),
        color_mode='grayscale',
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        shuffle=False
    )

    return train_generator, validation_generator

if __name__ == "__main__":
    # fast test
    try:
        train_gen, val_gen = get_data_generators()
        print(f"Classes found: {train_gen.class_indices}")
    except Exception as e:
        print(f"Error: {e}")
