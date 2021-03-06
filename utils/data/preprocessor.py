from __future__ import absolute_import
import os.path as osp

from PIL import Image
import torch
import numpy as np
import cv2

import av
from av import time_base as AV_TIME_BASE
from sklearn.preprocessing import MultiLabelBinarizer

class Preprocessor(object):
    def __init__(self, data_dir, labels, transform=None):
        super(Preprocessor, self).__init__()
        self.data_dir = data_dir
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, indices):
        if isinstance(indices, (tuple, list)):
            return [self._get_single_item(index) for index in indices]
        return self._get_single_item(indices)

    def _get_single_item(self, index):
        line = self.labels[index]
        sp_line = line.split(",")
        fname, tag = sp_line[0], int(sp_line[1])
        fpath = osp.join(self.data_dir, fname)

        img = Image.open(fpath).convert('RGB')

        if self.transform is not None:
            img = self.transform(img)

        return img, fname, tag

class TrainPreprocessor(object):
    def __init__(self, data_dir, labels, transform=None):
        super(TrainPreprocessor, self).__init__()
        self.data_dir = data_dir
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, indices):
        if isinstance(indices, (tuple, list)):
            return [self._get_single_item(index) for index in indices]
        return self._get_single_item(indices)

    def _get_single_item(self, index):
        line = self.labels[index]
        sp_line = line.split(",")
        fname, tag = sp_line[0], int(sp_line[1])
        fpath = osp.join(self.data_dir, fname)

        img = Image.open(fpath).convert('RGB')

        if self.transform is not None:
            img = self.transform(img)

        return img, tag

#label mode:
#multi-class
#single-class
class VideoTrainPreprocessor(object):
    def __init__(self, data_dir, labels, num_frames = 1, transform = None, label_mode = 'multi-class'):
        super(VideoTrainPreprocessor, self).__init__()
        self.data_dir = data_dir
        self.labels = labels
        self.transform = transform
        self.num_frames = num_frames
        #self.cap = cv2.VideoCapture()
        self.current_idx = None
        self.mlb = None
        self._init_binarizer()
        self.label_mode = label_mode

    def __len__(self):
        return len(self.labels)
    
    def _init_binarizer(self):
        self.mlb = MultiLabelBinarizer()

        max_label = 0
        for line in self.labels:
            sp_line = line.split(",")

            for el in sp_line:
                try:
                    el = int(el)
                    max_label = max(el, max_label)
                except (ValueError, TypeError):
                    pass
        self.mlb.fit([np.arange(0, max_label + 1)])

    def __getitem__(self, indices):
        if isinstance(indices, (tuple, list)):
            items = []
            for index in indices:
                items.append(*(self._get_multi_items(index)))
            print(items)
            return items[0]
            #return [self._get_multi_items(index) for index in indices]
        #print('idx:' , indices)
        return self._get_multi_items(indices)
            
    def _get_single_item(self, index, cap, video_stream, frames):
        frame = self._get_single_frame(index, cap, video_stream, frames)
        img = frame.to_image()
        if self.transform is not None:
            img = self.transform(img)
        
        return img

    def _get_multi_items(self, index):
        #got video index        
        line = self.labels[index]

        sp_line = line.split(",")
        fname = sp_line[0]
        tags = []
        for el in sp_line:
            try:
                tags.append(int(el))
            except (ValueError, TypeError):
                pass
        #transform tags
        if self.label_mode == 'multi-class':
            tags = self.mlb.transform([tags])[0]
            tags = tags.reshape(1, tags.shape[0])
        elif self.label_mode == 'single-class':
            tags = tags[0]
        fpath = osp.join(self.data_dir, fname)

        #open container
        cap = av.open(fpath, mode = 'r')
        #get video stream
        video_stream = next(s for s in cap.streams if s.type == 'video')
        num_frames = video_stream.frames - 30
        #fix
        if num_frames < 0:
            num_frames = int(video_stream.frames)

        if self.num_frames == 1:
            #make it stable for now
            img = self._get_single_item(0, cap, video_stream, num_frames)
            return img, tags
            #return img, int(tag)
           
        t = np.random.choice(num_frames, size=self.num_frames)
        t = np.sort(t)
        frames = torch.stack([self._get_single_item(idx, cap, video_stream, num_frames) for idx in t])
        
        return frames, np.repeat(tags, self.num_frames, 0)
        
    def _get_single_frame(self, index, cap, video_stream, frames):
        cap.seek(int(int((index * AV_TIME_BASE) / video_stream.average_rate)), 'frame')
        got_frame = False

        for packet in cap.demux(video_stream):
            if not got_frame:
                for frame in packet.decode():
                    if frame is not None:
                        return frame
                        

#mode example:
#all_frames
#first_frame
#random_frames

class VideoTestPreprocessor(VideoTrainPreprocessor):
    def __init__(self, data_dir, labels, num_frames = 10, transform = None, mode = "random_frames", label_mode = 'multi-class'):
        super(VideoTestPreprocessor, self).__init__(data_dir, labels, num_frames, transform)
        self.data_dir = data_dir
        self.labels = labels
        self.transform = transform
        self.num_frames = num_frames
        #self.cap = cv2.VideoCapture()
        self.current_idx = None
        self.mode = mode
        self.label_mode = label_mode

    def _get_multi_items(self, index):
        #got video index        
        line = self.labels[index]

        #labels in eval file should be arrange as:
        #fname,tag_i,...,tag_n
        sp_line = line.split(",")
        fname = sp_line[0]
        tags = []
        for el in sp_line:
            try:
                tags.append(int(el))
            except (ValueError, TypeError):
                pass
        tags_ = torch.ones(3).mul_(-1)
        #transform tags
        if self.label_mode == 'multi-class':
            tags = self.mlb.transform([tags])[0]
        elif self.label_mode == 'single-class':
            for p in range(len(tags)):
                tags_[p] = tags[p]
        #tags = tags.reshape(1, tags.shape[0])
        fpath = osp.join(self.data_dir, fname)
        #open container
        cap = av.open(fpath, mode = 'r')
        #get video stream
        video_stream = next(s for s in cap.streams if s.type == 'video')

        n_frames = int(video_stream.frames) - 15
        #some videos are too short
        if n_frames <= 0:
            n_frames = int(video_stream.frames)

        if self.mode == "first_frame":
            return self._get_single_item(0, cap, video_stream, 0), tags_
        elif self.mode == "random_frames":
            t = np.random.choice(n_frames, size=self.num_frames)
            t = np.sort(t)
            frames = torch.stack([self._get_single_item(idx, cap, video_stream, self.num_frames) for idx in t])
            #print(frames)
            return frames, tags_
        elif self.mode == "all_frames":
            frames = torch.stack([self._get_single_item(idx, cap, video_stream, self.num_frames) for idx in range(n_frames)])
            return frames, tags_