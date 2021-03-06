import math, shutil, os, time
import numpy as np
import scipy.io as sio
import argparse
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim
import torch.utils.data
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision.models as models
from torchsummary import summary
from torch.autograd import gradcheck
from torch.optim.lr_scheduler import ReduceLROnPlateau

from EyeDataRand import ITrackerData
from EyeTrackerModel import ITrackerModel

# Change there flags to control what happens.
doLoad = False # Load checkpoint at the beginning
doTest = False # Only run test, no training

workers = 8
epochs = 15
base_lr = 1e-3
momentum = 0.9
weight_decay = 1e-4
print_freq = 10
prec1 = 0
best_prec1 = 1e20
lr = base_lr
K_folds = 4
count_test = 0
count = 0

# # GPU available
# os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
# os.environ["CUDA_VISIBLE_DEVICES"] = '0,1,3,4'

# def init_weights(m):
#     if type(m) == nn.Linear:
#         torch.nn.init.xavier_uniform(m.weight)
#         m.bias.data.fill_(0.01)

def main():

    # GPU available
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = '0, 1, 2, 3'
    print('__Number CUDA Devices:', torch.cuda.device_count())
    print('Active CUDA Device: GPU', torch.cuda.current_device())

    #batch size
    batch_size = torch.cuda.device_count() * 64 # Change if out of cuda memory

    global args, best_prec1, weight_decay, momentum

    model = ITrackerModel()
    model = torch.nn.DataParallel(model, device_ids=[0, 1, 2, 3])
    model.cuda()
    # model.apply(init_weights)
    imSize=(224, 224)
    cudnn.benchmark = True

    epoch = 0
    if doLoad:
        saved = load_checkpoint()
        if saved:
            print('Loading checkpoint for epoch %05d with loss %.5f (which is L2 = mean of squares)...' % (saved['epoch'], saved['best_prec1']))
            state = saved['state_dict']
            try:
                model.module.load_state_dict(state)
            except:
                model.load_state_dict(state)
            epoch = saved['epoch']
            best_prec1 = saved['best_prec1']
        else:
            print('Warning: Could not read checkpoint!');

    
    dataTrain = ITrackerData(split='train', imSize=imSize)
    dataVal = ITrackerData(split='val', imSize=imSize)
    dataTest = ITrackerData(split='test', imSize=imSize)
   
    train_loader = torch.utils.data.DataLoader(
        dataTrain,
        batch_size=batch_size, shuffle=True,
        num_workers=workers, pin_memory=True)

    val_loader = torch.utils.data.DataLoader(
        dataVal,
        batch_size=batch_size, shuffle=True,
        num_workers=workers, pin_memory=True)

    test_loader = torch.utils.data.DataLoader(
        dataTest,
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        pin_memory=True
    )



    criterion = nn.MSELoss().cuda()

    # optimizer = torch.optim.SGD(model.parameters(), lr,
    #                             momentum=momentum,
    #                             weight_decay=weight_decay)

    # schedular = ReduceLROnPlateau(optimizer=optimizer, mode='min', factor=0.3, patience=2, verbose=True, min_lr=0)

    optimizer = torch.optim.Adam(model.parameters(), lr,
                                 weight_decay=weight_decay)
    # summary(model, input_size=[(3, 224, 224), (3, 224, 224), (3, 224, 224), (1, 25, 25)])
    print(models)
    # counter
    counter = 0
    # Quick test
    if doTest:
        validate(val_loader, model, criterion, epoch)
        return

    for epoch in range(0, epoch):
        adjust_learning_rate(optimizer, epoch)

    for k in range(K_folds):
        print('K fold Number : {}'.format(k))
        for epoch in range(epoch, epochs):
            adjust_learning_rate(optimizer, epoch)

        # train for one epoch
            train(train_loader, model, criterion, optimizer, epoch)

        # evaluate on validation set
            prec1 = validate(test_loader, model, criterion, epoch)

        # learning rate schedular

        # schedular.step(prec1)

        # remember best prec@1 and save checkpoint
            is_best = prec1 < best_prec1
            best_prec1 = min(prec1, best_prec1)
            save_checkpoint({
                'epoch': epoch + 1,
                'state_dict': model.state_dict(),
                'best_prec1': best_prec1,
            }, is_best)

        # if epoch == 15:
        #     optimizer = torch.optim.SGD(model.parameters(), lr,
        #                                 momentum=momentum,
        #                                 weight_decay=weight_decay)
        # if counter == 3:
        #     adjust_learning_rate(optimizer)
        #     counter = 0


def train(train_loader, model, criterion,optimizer, epoch):
    global count
    batch_time = AverageMeter()
    data_time = AverageMeter()
    losses = AverageMeter()

    # switch to train mode
    model.train()

    end = time.time()

    for i, (row, imFace, imEyeL, imEyeR, faceGrid, gaze) in enumerate(train_loader):
        
        # measure data loading time
        data_time.update(time.time() - end)
        imFace = imFace.cuda(async=True)
        imEyeL = imEyeL.cuda(async=True)
        imEyeR = imEyeR.cuda(async=True)
        faceGrid = faceGrid.cuda(async=True)
        gaze = gaze.cuda(async=True)
        
        imFace = torch.autograd.Variable(imFace, requires_grad=True)
        imEyeL = torch.autograd.Variable(imEyeL)
        imEyeR = torch.autograd.Variable(imEyeR)
        faceGrid = torch.autograd.Variable(faceGrid)
        gaze = torch.autograd.Variable(gaze)

        # compute output
        output = model(imFace, imEyeL, imEyeR, faceGrid)

        loss = criterion(output, gaze)
        
        losses.update(loss.item(), imFace.size(0))

        # compute gradient and do SGD step
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # measure elapsed time
        batch_time.update(time.time() - end)
        end = time.time()

        count=count+1

        print('Epoch (train): [{0}][{1}/{2}]\t'
                  'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                  'Data {data_time.val:.3f} ({data_time.avg:.3f})\t'
                  'Loss {loss.val:.4f} ({loss.avg:.4f})\t'.format(
                   epoch, i, len(train_loader), batch_time=batch_time,
                   data_time=data_time, loss=losses))

def validate(val_loader, model, criterion, epoch):
    global count_test
    batch_time = AverageMeter()
    data_time = AverageMeter()
    losses = AverageMeter()
    lossesLin = AverageMeter()

    # switch to evaluate mode
    model.eval()
    end = time.time()
    with torch.no_grad():

        oIndex = 0
        for i, (row, imFace, imEyeL, imEyeR, faceGrid, gaze) in enumerate(val_loader):
        # measure data loading time
            data_time.update(time.time() - end)
            imFace = imFace.cuda(async=True)
            imEyeL = imEyeL.cuda(async=True)
            imEyeR = imEyeR.cuda(async=True)
            faceGrid = faceGrid.cuda(async=True)
            gaze = gaze.cuda(async=True)

            imFace = torch.autograd.Variable(imFace)
            imEyeL = torch.autograd.Variable(imEyeL)
            imEyeR = torch.autograd.Variable(imEyeR)
            faceGrid = torch.autograd.Variable(faceGrid)
            gaze = torch.autograd.Variable(gaze)
            # compute output
            output = model(imFace, imEyeL, imEyeR, faceGrid)

            loss = criterion(output, gaze)

            lossLin = output - gaze
            lossLin = torch.mul(lossLin,lossLin)
            lossLin = torch.sum(lossLin,1)
            lossLin = torch.mean(torch.sqrt(lossLin))

            losses.update(loss.item(), imFace.size(0))
            lossesLin.update(lossLin.item(), imFace.size(0))

            # compute gradient and do SGD step
            # measure elapsed time
            batch_time.update(time.time() - end)
            end = time.time()


            print('Epoch (val): [{0}][{1}/{2}]\t'
                  'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                  'Loss {loss.val:.4f} ({loss.avg:.4f})\t'
                  'Error L2 {lossLin.val:.4f} ({lossLin.avg:.4f})\t'.format(
                    epoch, i, len(val_loader), batch_time=batch_time,
                   loss=losses,lossLin=lossesLin))

        return lossesLin.avg

CHECKPOINTS_PATH = '../Eyetracking_pytorch'

def load_checkpoint(filename='best_checkpoint.pth.tar'):
    filename = os.path.join(CHECKPOINTS_PATH, filename)
    print(filename)
    if not os.path.isfile(filename):
        return None
    state = torch.load(filename)
    return state

def save_checkpoint(state, is_best, filename='checkpoint.pth.tar'):
    if not os.path.isdir(CHECKPOINTS_PATH):
        os.makedirs(CHECKPOINTS_PATH, 0o777)
    bestFilename = os.path.join(CHECKPOINTS_PATH, 'best_' + filename)
    filename = os.path.join(CHECKPOINTS_PATH, filename)
    torch.save(state, filename)
    if is_best:
        shutil.copyfile(filename, bestFilename)


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def adjust_learning_rate(optimizer, epochs):
    """Sets the learning rate to the initial LR decayed by 10 every 30 epochs"""
    lr = base_lr * (0.1 ** (epochs/5))
    print('Learning Rate decreased to {}'.format(lr))
    for param_group in optimizer.state_dict()['param_groups']:
        param_group['lr'] = lr
#

if __name__ == "__main__":
    main()
    print('DONE')
