import numpy as np
from keras.layers import Layer
from keras.layers import Input, Conv2D, Dense, Flatten, MaxPool2D, concatenate, Dropout
from keras.models import Model


class ScaledSigmoid(Layer):
    def __init__(self, alpha, beta, **kwargs):
        self.alpha = alpha
        self.beta = beta
        super(ScaledSigmoid, self).__init__(**kwargs)

    def build(self, input_shape):
        super(ScaledSigmoid, self).build(input_shape)

    def call(self, x, mask=None):
        return self.alpha / (1 + np.exp(-x / self.beta))

    def get_output_shape_for(self, input_shape):
        return input_shape


# activation functions
activation = 'relu'
last_activation = "elu"


# eye model
def get_eye_model(img_cols, img_rows, img_ch):

    eye_img_input = Input(shape=(img_cols, img_rows, img_ch))
    h = Conv2D(64, (3, 3), activation=activation, padding='same')(eye_img_input)
    h = MaxPool2D(pool_size=(2, 2), strides=(2,2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(128, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(128, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2,2), strides=(2,2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(256, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(256, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(256, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2,2), strides=(2,2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2,2), strides=(2,2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2,2), strides=(2,2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    # h = (Dropout(0.25))(h)
    out = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)

    model = Model(inputs=eye_img_input, outputs=out)

    return model


# face model
def get_face_model(img_cols, img_rows, img_ch):

    face_img_input = Input(shape=(img_cols, img_rows,img_ch))
    h = Conv2D(64, (3, 3), activation=activation, padding='same')(face_img_input)
    h = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(128, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(128, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(256, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(256, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(256, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)
    # h = (Dropout(0.25))(h)

    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    h = Conv2D(512, (3, 3), activation=activation, padding='same')(h)
    # h = (Dropout(0.25))(h)
    out = MaxPool2D(pool_size=(2, 2), strides=(2, 2))(h)

    model = Model(inputs=face_img_input, outputs=out)

    return model


# final model
def get_eye_tracker_model(img_cols, img_rows, img_ch):

    # get partial models
    eye_net = get_eye_model(img_cols, img_rows, img_ch)
    face_net_part = get_face_model(img_cols, img_rows, img_ch)

    # right eye model
    right_eye_input = Input(shape=(img_cols, img_rows, img_ch))
    right_eye_net = eye_net(right_eye_input)

    # left eye model
    left_eye_input = Input(shape=(img_cols, img_rows,img_ch))
    left_eye_net = eye_net(left_eye_input)

    # face model
    face_input = Input(shape=(img_cols, img_rows,img_ch))
    face_net = face_net_part(face_input)

    # face grid
    face_grid = Input(shape=(25, 25, 1))

    # dense layers for eyes
    e = concatenate([left_eye_net, right_eye_net])
    e = Flatten()(e)
    fc_e1 = Dense(128, activation=activation)(e)
    # fc_e1 = Dropout(0.5)(fc_e1)

    # dense layers for face
    f = Flatten()(face_net)
    fc_f1 = Dense(128, activation=activation)(f)
    fc_f2 = Dense(64, activation=activation)(fc_f1)
    # fc_f2 = Dropout(0.5)(fc_f2)

    # dense layers for face grid
    fg = Flatten()(face_grid)
    fc_fg1 = Dense(256, activation=activation)(fg)
    fc_fg2 = Dense(128, activation=activation)(fc_fg1)
    # fc_fg2 = Dropout(0.5)(fc_fg2)

    # combining face and face grid in one flatten layer

    # final dense layers
    h = concatenate([fc_e1, fc_f2, fc_fg2])
    fc1 = Dense(128, activation=activation)(h)
    # fc1 = Dropout(0.5)(fc1)
    fc2 = Dense(2, activation=last_activation)(fc1)

    # final model
    final_model = Model(
        inputs=[right_eye_input, left_eye_input, face_input, face_grid],
        outputs=[fc2])

    return final_model
