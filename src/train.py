
import os
import matplotlib.pyplot as plt
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
from src.data_loader import get_data_generators
from src.model import build_model

# Constants
EPOCHS = 100
MODEL_PATH = 'src/models/focus_guard.h5'

def plot_history(history):
    """
    Plots training accuracy and loss graphs.
    """
    acc = history.history['accuracy']
    val_acc = history.history['val_accuracy']
    loss = history.history['loss']
    val_loss = history.history['val_loss']

    epochs_range = range(len(acc))

    plt.figure(figsize=(12, 6))
    
    # Accuracy Plot
    plt.subplot(1, 2, 1)
    plt.plot(epochs_range, acc, label='Training Accuracy')
    plt.plot(epochs_range, val_acc, label='Validation Accuracy')
    plt.legend(loc='lower right')
    plt.title('Training and Validation Accuracy')

    # Loss Plot
    plt.subplot(1, 2, 2)
    plt.plot(epochs_range, loss, label='Training Loss')
    plt.plot(epochs_range, val_loss, label='Validation Loss')
    plt.legend(loc='upper right')
    plt.title('Training and Validation Loss')
    
    plt.savefig('training_results.png')
    print("Graphs saved to training_results.png")

def train():
    # 1. Get Data
    train_gen, val_gen = get_data_generators()
    num_classes = train_gen.num_classes
    print(f"Detected {num_classes} classes: {list(train_gen.class_indices.keys())}")

    # 2. Build Model
    model = build_model(num_classes=num_classes)
    
    # 3. Callbacks (Save best model, stop early if no improvement)
    checkpoint = ModelCheckpoint(
        MODEL_PATH,
        monitor='val_accuracy',
        save_best_only=True,
        mode='max',
        verbose=1
    )
    
    early_stop = EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True,
        verbose=1
    )
    
    reduce_lr = ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.2,
        patience=5,
        min_lr=0.00001,
        verbose=1
    )

    # 4. Train (with Class Weights to handle imbalance)
    from sklearn.utils import class_weight
    import numpy as np

    # Calculate weights based on training data
    # y_train are the labels. We need to get them from the generator carefully or just use the class counts.
    # The generator 'classes' attribute gives us the class indices for all samples.
    class_weights = class_weight.compute_class_weight(
        class_weight='balanced',
        classes=np.unique(train_gen.classes),
        y=train_gen.classes
    )
    # Convert to dict for Keras (Explicit comprehension to fix linter)
    class_weights_dict = {i: weight for i, weight in enumerate(class_weights)}
    print(f"Computed Class Weights: {class_weights_dict}")

    print("Starting Training (with Class Balancing)...")
    history = model.fit(
        train_gen,
        epochs=EPOCHS,
        validation_data=val_gen,
        callbacks=[checkpoint, early_stop, reduce_lr],
        class_weight=class_weights_dict
    )

    # 5. Save Final & Plot
    model.save('src/models/focus_guard_final.h5')
    plot_history(history)
    print("Training Complete!")

if __name__ == "__main__":
    # Ensure model directory exists
    os.makedirs('src/models', exist_ok=True)
    train()
