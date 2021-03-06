import numpy as np
import keras
from keras import Input, Model
from keras.layers import Conv3D, MaxPooling3D, UpSampling3D, ELU, Dropout, ReLU, MaxPooling2D, UpSampling2D, Conv2D, \
    LocallyConnected2D, SeparableConv2D, Dense, Flatten, Reshape, Conv1D, MaxPooling1D, UpSampling1D


class STFTNet:
    def __init__(self):
        self.__model__ = keras.Model

    def down(self, input, neurons=32):
        conv = SeparableConv2D(
            filters=neurons,
            kernel_regularizer=keras.regularizers.l2(.01),
            kernel_size=(3, 3),
            padding='same'
        )(input)
        conv = ReLU()(conv)
        conv = MaxPooling2D((1, 2))(conv)
        conv = Dropout(.2)(conv)
        return conv

    def init(self, input_shape=(1, 2, 3)):
        input = Input(batch_shape=(None,) + tuple(input_shape))

        down1 = self.down(input, input_shape[-1]*2)
        down2 = self.down(down1, input_shape[-1]*4)
        down3 = self.down(down2, input_shape[-1]*8)

        flat = Flatten()(down3)

        f1 = Dense(256, activation='relu')(flat)
        drop = Dropout(.5)(f1)
        f1 = Dense(256, activation='relu')(drop)
        drop = Dropout(.5)(f1)
        # f1 = Dense(64, activation='relu')(drop)
        #drop = Dropout(.5)(f1)
        f2 = Dense(2, activation='softmax')(drop)

        self.__model__ = Model(inputs=input, outputs=f2)
        print(self.__model__.summary())

        return self.__model__

    def compile(self):
        opt = keras.optimizers.adam(
            learning_rate=.0008,
        )
        self.__model__.compile(
            optimizer=opt,
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        return self.__model__

    def train_offline(self):
        pass

    def test_s2(self, s2=np.ndarray):
        pass

    def continue_train_s2(self, s2=np.ndarray):
        pass

    def test_s3(self, s3=np.ndarray):
        pass