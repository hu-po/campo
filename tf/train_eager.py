import datetime
from pathlib import Path
import re
import tensorflow as tf
import tensorflow_hub as hub

# Enable eager execution
tf.enable_eager_execution()
tfe = tf.contrib.eager

# Load datasets (USE tf.data API)
root_dir = Path.cwd()
data_dir = root_dir / 'data' / 'images_and_annotations'
train_dir = data_dir / 'PSI_Tray031' / 'tv'
test_dir = data_dir / 'PSI_Tray032' / 'tv'
model_dir = root_dir / 'model'
PLANT_START_DATE = datetime.datetime(2015, 12, 14, hour=12, minute=54, second=51)
PLANT_AGE_MULT = 1.5 * 2592000  # Age of plant in seconds for normalizing


def plant_age_from_filename(filename):
    # Sample filename: PSI_Tray031_2015-12-26--17-38-25_top.png
    filename_regex = re.search(r'(201\d)-(\d+)-(\d+)--(\d+)-(\d+)-(\d+)', str(filename))
    year, month, day, hour, min, sec = (int(_) for _ in filename_regex.groups())
    date = datetime.datetime(year, month, day, hour=hour, minute=min, second=sec)
    plant_age = date - PLANT_START_DATE
    # Normalize age between 0 and 1
    return plant_age.total_seconds() / PLANT_AGE_MULT


def _parse_single(filename, label):
    # Decode and convert image to appropriate type
    image = tf.image.decode_png(tf.read_file(filename))
    # image = tf.image.convert_image_dtype(image, tf.float32)
    # Resize according to module requirements
    image = tf.image.resize_images(image, [224, 224])
    return image, label


class AgeModel(tf.keras.Model):
    def __init__(self):
        super(AgeModel, self).__init__()
        self.encoder = tf.keras.applications.resnet50.ResNet50(include_top=False,
                                                               weights='imagenet',
                                                               pooling='max',
                                                               )
        self.head_1 = tf.keras.layers.Dense(128, activation='relu')
        self.head_2 = tf.keras.layers.Dense(64, activation='relu')
        self.head_3 = tf.keras.layers.Dense(1, activation=None)

    def predict(self, inputs):
        result = self.encoder(inputs)
        result = self.head_1(result)
        result = self.head_2(result)
        result = self.head_3(result)
        return result


def loss(model, input, target):
    error = model.predict(input) - target
    return tf.reduce_mean(tf.square(error))


def grad(model, input, target):
    with tfe.GradientTape() as tape:
        loss_value = loss(model, input, target)
    return tape.gradient(loss_value, model.variables)


SHUFFLE_BUFFER = 1
NUM_EPOCHS = 10
LEARNING_RATE = 0.01
BATCH_SIZE = 1

# Create a constants with filenames and plant age labels
filenames = tf.constant(list(str(file) for file in train_dir.glob('*.png')))
plant_ages = list(map(plant_age_from_filename, train_dir.glob('*.png')))
labels = tf.constant(plant_ages)
dataset = tf.data.Dataset.from_tensor_slices((filenames, labels))

dataset = dataset.map(lambda filename, label: _parse_single(filename, label))
dataset = dataset.shuffle(SHUFFLE_BUFFER).repeat(NUM_EPOCHS).batch(BATCH_SIZE)

model = AgeModel()
optimizer = tf.train.GradientDescentOptimizer(learning_rate=LEARNING_RATE)

# Fix comes from https://stackoverflow.com/questions/49658802/how-can-i-use-tf-data-datasets-in-eager-execution-mode
x, y = tfe.Iterator(dataset).next()
print(f'Initial loss {loss(model, x, y)}')

for (i, (image, target)) in enumerate(tfe.Iterator(dataset)):
    grads = grad(model, image, target)
    optimizer.apply_gradients(zip(grads, model.variables))
    if i % 2 == 0:  # nan errors on the losses after this point
        print(f'Step {i} Loss is {loss(model, image, target)}')
