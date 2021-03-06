from __future__ import print_function, absolute_import
import argparse
import os.path as osp
import os

import numpy as np
import sys
import torch
from torch import nn
from torch.backends import cudnn
from torch.utils.data import DataLoader
import torchvision.transforms as T
from utils.data.preprocessor import Preprocessor, VideoTestPreprocessor
from utils.meters import AverageMeter

import models
import errno

def mkdir_if_missing(dir_path):
    try:
        os.makedirs(dir_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

def collate_batch(batch):
    #print(batch)
    out_batch = torch.stack([b[0] for b in batch], 0)
    out_tags = [b[1] for b in batch]
    return out_batch, out_tags

def get_data(data_dir, ann_file, height, width, batch_size, workers):

    normalizer = T.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])


    test_transformer = T.Compose([
        T.Resize(256),
        T.CenterCrop(224),
        T.ToTensor(),
        normalizer,
    ])

    #open annotation_file
    labels = None
    with open(ann_file) as infile:
        labels = infile.readlines()
    infile.close()


    data_loader = DataLoader(
        VideoTestPreprocessor(data_dir, labels, transform=test_transformer),
        batch_size=1, num_workers=workers,
        shuffle=False, pin_memory=True)

    return data_loader


def main(args):

    
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    cudnn.benchmark = False
    cudnn.enabled = True
 

    batch_size = 1 if args.frames_mode

    data_loader = \
        get_data(args.data_dir, args.ann_file, args.height,
                 args.width, args.batch_size, args.workers)


    model = models.create(args.arch, weigths = args.weights,  gpu = args.gpu, n_classes = 63)

    if args.gpu:
        model = nn.DataParallel(model).cuda()
    else:
        model = nn.DataParallel(model)
    model.eval()

    print(model)
    acc = AverageMeter()

    with torch.no_grad():
        for i, (input, tags) in enumerate(data_loader):
            if args.gpu:
                input = input.cuda()
            output = torch.squeeze(model(input))

            if args.gpu:
                output = output.cpu()
            res = accuracy(output, tags, (args.topk,)) 
            acc.update(res)

            if i % args.print_freq == 0:
                print('Test: [{0}/{1}]\t'
                      'Prec@1 {acc.val:.3f} ({acc.avg:.3f})\t'.format(
                      i, len(data_loader), acc=acc))     
        
        print(' * Prec@1 {acc.avg:.3f}'.format(acc=acc) )


def accuracy(output, tags, topk=(5,)):
    with torch.no_grad():
        maxk = max(topk)

        if len(tags) == 1:
            return ch_metric(output, tags[0], maxk)

        else:
            res = 0
            for i in range(len(tags)):
                res += ch_metric(output[i], tags[i], maxk)
            res /= len(tags)
            return res

def ch_metric(output, tags, maxk):
    _, pred = output.topk(maxk)
    pred = set(pred.numpy())
    tags = set(tags)
    
    return len(set.intersection(pred, tags)) / len(set.union(pred, tags))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Network evaluation")
    # data


    parser.add_argument('-b', '--batch-size', type=int, default=64)
    parser.add_argument('-j', '--workers', type=int, default=4)
    parser.add_argument('--height', type=int, default = 224)
    parser.add_argument('--width', type=int, default = 224)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--topk', '-t', type = int, default = 5)
    # model
    parser.add_argument('-a', '--arch', type=str, default='resnet50',
                        choices=models.names())
    parser.add_argument('--weights', '-w', type = str, metavar = 'PATH', help='path to the checkpoint')
    parser.add_argument('--ann_file', type=str, metavar='PATH', help = "path to the annotation file")
    parser.add_argument('--data_dir', type=str, metavar='PATH', help = "path to the data folder")
    parser.add_argument('--print-freq', '-p', default=100, type=int,
                    metavar='N', help='print frequency (default: 10)')

    parser.add_argument('--gpu', action='store_true',
                        help="use gpu")
    

    main(parser.parse_args())
