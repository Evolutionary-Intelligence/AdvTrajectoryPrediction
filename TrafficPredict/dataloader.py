import logging
import os
import pickle
import random

import numpy as np

class TrafficPredictDataLoader:
    def __init__(
        self, batch_size=50, obs_length=4, pred_length=6, infer=True
    ):
        """
        Initialiser function for the DataLoader class
        params:
        batch_size : Size of the mini-batch
        seq_length : Sequence length to be considered  21
        datasets : The indices of the datasets to use
        forcePreProcess : Flag to forcefully preprocess the data again from csv files
        """
        random.seed(42)
        np.random.seed(42)
        # List of data directories where raw data resides
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dirs = os.path.join(self.root_dir, "data/prediction_train/")
        self.dataset_cnt = len(os.listdir(self.data_dirs))
        self.dataset_idx = sorted(os.listdir(self.data_dirs))
        np.random.shuffle(self.dataset_idx)
        self.train_data_dirs = self.dataset_idx[: int(self.dataset_cnt * 0.9)]
        if infer == True:
            self.train_data_dirs = self.dataset_idx[int(self.dataset_cnt * 0.9) :]
        self.infer = infer

        # Store the arguments
        self.batch_size = batch_size
        self.seq_length = obs_length + pred_length
        self.obs_length = obs_length
        self.pred_length = pred_length

        data_file = os.path.join(self.root_dir, "data", "trajectories.cpkl")
        if infer == True:
            data_file = os.path.join(self.root_dir, "data", "test_trajectories.cpkl")

        self.min_position_x = 1000
        self.max_position_x = -1000
        self.min_position_y = 1000
        self.max_position_y = -1000

        for ind_directory, directory in enumerate(self.train_data_dirs):
            file_path = os.path.join(self.root_dir, "data/prediction_train", directory)
            data = np.genfromtxt(file_path, delimiter=" ")
            self.min_position_x = min(self.min_position_x, min(data[:, 3]))
            self.max_position_x = max(self.max_position_x, max(data[:, 3]))
            self.min_position_y = min(self.min_position_y, min(data[:, 4]))
            self.max_position_y = max(self.max_position_y, max(data[:, 4]))


    def generate_data(self):
        for _, directory in enumerate(self.train_data_dirs):
            file_path = os.path.join(self.root_dir, "data/prediction_train", directory)
            data = np.genfromtxt(file_path, delimiter=" ")
            data = data[~(data[:, 2] == 5)]
            numFrames = len(np.unique(data[:, 0]))
            numSlices = numFrames // self.seq_length

            for slice_id in range(numSlices):
                input_data = {
                    "observe_length": self.obs_length,
                    "predict_length": self.pred_length,
                    "objects": {}
                }

                # fill data
                for frame_id in range(slice_id*self.seq_length, (slice_id+1)*self.seq_length):
                    frame_data = data[data[:, 0] == frame_id, :]
                    for obj_index in range(frame_data.shape[0]):
                        obj_data = frame_data[obj_index, :]
                        obj_id = obj_data[1]
                        if obj_id not in input_data["objects"]:
                            input_data["objects"][int(obj_id)] = {
                                "type": self.class_objtype(obj_data[2]),
                                "observe_trace": np.zeros((self.obs_length,2)),
                                "future_trace": np.zeros((self.pred_length,2)),
                                "predict_trace": np.zeros((self.pred_length,2)),
                                "frame": slice_id*self.seq_length,
                                "length": 0
                            }
                        obj = input_data["objects"][obj_id]
                        if obj["length"] < self.seq_length and obj["frame"] == frame_id:
                            if obj["length"] < self.obs_length:
                                obj["observe_trace"][obj["length"], 0] = obj_data[3]
                                obj["observe_trace"][obj["length"], 1] = obj_data[4]
                            else:
                                obj["future_trace"][obj["length"]-self.obs_length, 0] = obj_data[3]
                                obj["future_trace"][obj["length"]-self.obs_length, 1] = obj_data[4]
                            obj["length"] += 1
                            obj["frame"] += 1

                # remove invalid data
                invalid_obj_ids = []
                for obj_id, obj in input_data["objects"].items():
                    if obj["length"] != self.seq_length:
                        invalid_obj_ids.append(obj_id)
                    else:
                        del obj["length"]
                        del obj["frame"]
                for invalid_obj_id in invalid_obj_ids:
                    del input_data["objects"][invalid_obj_id]

                yield input_data

    def preprocess(self, input_data):
        x = []
        for frame_id in range(self.seq_length):
            frame_data = np.zeros((len(input_data["objects"]), 4))
            index = 0
            for obj_id, obj in input_data["objects"].items():
                frame_data[index, 0] = obj_id
                frame_data[index, 3] = obj["type"]
                if frame_id < self.obs_length:
                    pos = obj["observe_trace"][frame_id, :]
                else:
                    pos = obj["future_trace"][frame_id-self.obs_length, :]
                frame_data[index, 1] = (pos[0] - self.min_position_x) / (self.max_position_x - self.min_position_x) * 2 -1
                frame_data[index, 2] = (pos[1] - self.min_position_y) / (self.max_position_y - self.min_position_y) * 2 -1
                index += 1
            x.append(frame_data)
        return [x] # default batch_size=1

    def postprocess(self, input_data, ret_nodes):
        for frame_id in range(self.obs_length, self.seq_length):
            print(frame_id)
            frame_data = ret_nodes[frame_id]
            index = 0
            for obj_id, obj in input_data["objects"].items():
                print(index)
                obj["predict_trace"][frame_id-self.obs_length,0] = (frame_data[index,0] + 1) / 2 * (self.max_position_x - self.min_position_x) + self.min_position_x
                obj["predict_trace"][frame_id-self.obs_length,1] = (frame_data[index,1] + 1) / 2 * (self.max_position_y - self.min_position_y) + self.min_position_y
                index += 1
        return input_data

    def class_objtype(self, object_type):
        if object_type == 1 or object_type == 2:
            return 3
        elif object_type == 3:
            return 1
        elif object_type == 4:
            return 2
        else:
            return -1
