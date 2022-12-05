import torch
import numpy as np
import torchvision
import adabound
from tqdm import tqdm  # ������
from torch import nn
from torch.utils.data import DataLoader  # �������Ե���������װ����
from torchvision import datasets  # �������ݼ�
from torchvision import transforms  # ͼ��Ԥ�����
import torch.nn.functional as F  # ���ü����ReLU
import torch.optim as optim  # ʹ���Ż���
import matplotlib.pyplot as plt
import torchvision.models as models  # Ԥѵ��ģ��
from FocalLoss import FocalLoss  # ��ʧ����
from ResNet_CAB import resnet50

##################################################
# ���� python ����ҵ�� DR ͼ�����
# ����ģ��Ϊ ResNet50
# ����������� CAB ע�������ƺ� CBAM ע��������
##################################################


# Ѱ�������㷨
torch.backends.cudnn.enabled = True
torch.backends.cudnn.benchmark = True


##################################################
# ��������� kappa ��������
##################################################
def weight_kappa(result, test_num):
    weight = torch.zeros(5, 5)  # �½�һ�����󣬴��Ȩ��
    for i in range(5):
        for j in range(5):
            weight[i, j] = (i - j) * (i - j) / 16
    fenzi = 0
    for i in range(5):
        for j in range(5):
            fenzi = fenzi + result[i, j] * weight[i, j]
    fenmu = 0
    for i in range(5):
        for j in range(5):
            fenmu = fenmu + weight[i, j] * result[:, j].sum() * result[i, :].sum()

    weght_kappa = 1 - (fenzi / (fenmu / test_num))
    return float(weght_kappa)



##################################################
# ��������Ļ���
##################################################
def plot(matrix, acc):
    classes = 5  # 5 ����
    labels = ['No DR', 'Mild DR', 'Moderate DR', 'Servere DR', 'Proliferative DR']  # ��ǩ

    plt.imshow(matrix, cmap=plt.cm.Blues)

    # ����x������label
    plt.xticks(range(classes), labels, rotation=45)
    # ����y������label
    plt.yticks(range(classes), labels)
    # ��ʾcolorbar
    plt.colorbar()
    plt.xlabel('True Labels')
    plt.ylabel('Predicted Labels')
    plt.title('Confusion matrix (acc=' + str(acc) + ')')

    # ��ͼ�б�ע����/������Ϣ
    thresh = matrix.max() / 2
    for x in range(classes):
        for y in range(classes):
            # ע�������matrix[y, x]����matrix[x, y]
            info = int(matrix[y, x])
            plt.text(x, y, info,
                        verticalalignment='center',
                        horizontalalignment='center',
                        color="white" if info > thresh else "black")
    plt.tight_layout()
    plt.show()
    plt.savefig('result/confusion_matrix.png')
    plt.clf()  # ��ջ����������һ�λ�ͼ��ʱ�������


##################################################
# ѵ��
##################################################
def train(epoch):
    model.train()
    loop = tqdm(enumerate(train_loader), total=len(train_loader))
    running_loss = 0.0
    right = 0
    for batch_idx, data in loop:
        # ��ʼ��
        inputs, target = data
        inputs =inputs.cuda()
        target = target.cuda()
        optimizer.zero_grad()  # �Ż���ʹ��֮ǰ������

        # �Ż�ģ��
        outputs = model(inputs)
        loss = criterion(outputs, target)
        loss.backward()
        optimizer.step()
        # scheduler.step()

        # ��������ֵ�����ý���������������ķ�ʽ���
        running_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        # �ۼ�ʶ����ȷ��������
        right += (predicted == target).sum()
        # ������Ϣ
        loop.set_description(f'Epoch [{epoch}/{EPOCHS}]')
        loop.set_postfix(loss=running_loss / (batch_idx + 1), acc=float(right) / float(batch_size * (batch_idx + 1)))
    return loss.item()


##################################################
# ����
##################################################
def test():
    model.eval()
    correct = 0
    total = 0

    # ��������
    conf_matrix = torch.zeros(5, 5)

    with torch.no_grad():  # ȫ�̲������ݶ�
        for data in test_loader:
            images, labels = data  # ��¼ԭʼֵ
            images = images.cuda()
            labels = labels.cuda()
            outputs = model(images)  # ��ͼ�񶪽�ģ��ѵ�����õ�������
            _, predicted = torch.max(outputs.data, dim=1)  # ��ÿһ�����ֵ���±�
            # ����� outputs �� N * 1 �ģ�dim=1 ָ�������ŵ� 1 ��ά�ȣ�-->�����У����ǵ� 0 ��ά��
            # ��������ֵ�����ֵ�±��Լ����ֵ�Ƕ���
            total += labels.size(0)  # ��¼�ж����� labels
            correct += (predicted == labels).sum().item()  # ��ͬ�����ȡ����

            # ����������㣬����Ԥ��ֵ��������ʵֵ����Ӧ�ľ���ֵ��������������ڲ��Լ��г��ֵĴ���
            for i in range(labels.size()[0]):
                conf_matrix[int(outputs.argmax(1)[i])][int(labels[i])] += 1
            # print('���μ�����������Ϊ��\n', conf_matrix.int())
    conf_matrix = conf_matrix.int()  # תΪ int ���󣬷������ն˿�
    print('Accuracy on test set: %d %% ' % (100 * correct / total))
    print('��������Ϊ��\n', conf_matrix)
    print('weight_kappa��ֵΪ��', weight_kappa(conf_matrix, len(test_data)))

    plot(conf_matrix, correct / total)  # ����

    return correct / total


##################################################
# ������
##################################################
if __name__ == '__main__':
    image_size = 512  # ͼ���С 512 * 512
    batch_size = 8  # ����ô������Ϊ�Ʒ������ڴ����ޣ���̫��ֱ�Ӹ��� CUDA out of memory
    EPOCHS = 70  # �� 70 ��
    lr1 = 1e-3
    lr2 = 0.1

    ######################
    # Ԥ����
    ######################
    transform_train = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    ])
    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    ])

    # ʹ�� torchvision.datasets.ImageFolder ��ȡ���ݼ�ָ�� train �� test �ļ���
    train_data = torchvision.datasets.ImageFolder('DDR/train/', transform=transform_train)
    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)  # Windows �� num_workers ֻ������Ϊ 0����Ȼ�������Ʒ�������û���������

    test_data = torchvision.datasets.ImageFolder('DDR/test/', transform=transform_test)
    test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)


    ######################
    # ʵ����
    ######################
    # �°� ResNet ������ͼ���Сûǿ��Ҫ���ˣ���Ϊ��һ�� model.avgpool = nn.AdaptiveAvgPool2d((1, 1))����Ҳ������󲻹ܾ����������С��ֱ��ȡƽ��ֵ�������
    # model = ResidualNet("ImageNet", 34, 5, 'BAM')  # ���� BAM ע�������Ƶ� ResNet
    model = resnet50()  # ���� CBAM ע�������Ƶ� ResNet
    # model = ghost_net()  # GhostNet �Դ� SE ע�������ƣ�dropout ��
    # model = mobilenetv3()  # �Դ� drpout��SE
    # ����������������д�����ȫ���Ӳ㣬�������Ϊ 5��Ҳ������ 5 ���๤��
    in_channel = model.fc.in_features
    model.fc = nn.Linear(in_channel, 5)

    # ��һ�� dropout ��
    model.fc.register_forward_hook(lambda m, inp, out: F.dropout(out, p=0.5, training=m.training))

    # gpu ����
    model = model.cuda()

    ######################
    # ��ʧ����
    ######################
    # ��Ȩ��ʧ�����ķ����Ѿ�����
    # class_weight = torch.tensor([1880 / 1880, 1880 / 189, 1880 / 1344, 1880 / 71, 1880 / 275])  # ��ʧ������Ȩֵ���������������ɣ�����Ч����̫��
    # criterion = nn.CrossEntropyLoss(weight=class_weight)  # ʹ�ô�Ȩֵ�Ľ����غ������������������ƽ�������
    # criterion = nn.CrossEntropyLoss()
    criterion = FocalLoss(5)  # ʹ�� FocalLoss ����������ƽ�����ݣ�ʵ�ʲ���Ч�����
    criterion = criterion.cuda()

    ######################
    # �Ż���
    ######################
    # optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.5)  # momentum:ʹ�ô�������ģ�����Ż�ѵ������
    # optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=0.1)  # ���� L2 ���򻯣�����Ч��������զ��
    optimizer = adabound.AdaBound(model.parameters(), lr=lr1, final_lr=lr2)
    # scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda epoch: 1 / (epoch + 1), last_epoch=-1)  # �Զ�����ѧϰ��

    ######################
    # ѵ������
    ######################
    torch.cuda.empty_cache()  # ������棬�Ʒ��������Ǳ���������仰����ûʲô�ã��������С batch_size
    loss_list = []
    acc_list = []
    epoch_list = []

    for epoch in range(EPOCHS):
        # ����ʹ���˽����������Ҳ��������
        # print("----------��{}��ѵ����ʼ��----------".format(epoch + 1))
        loss = train(epoch)  # ѵ��һ��
        accuracy = test()  # ����һ��

        loss_list.append(loss)
        acc_list.append(accuracy)
        epoch_list.append(epoch)

    ######################
    # ��ͼ
    ######################
    plt.plot(epoch_list, loss_list)
    plt.plot(epoch_list, acc_list)
    plt.xlabel('epoch')
    plt.show()
    plt.savefig('result/loss-acc.png')
    plt.clf()