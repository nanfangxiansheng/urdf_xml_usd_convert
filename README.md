# object格式转换

首先得到的是在pm或者hssd_data下面的子模型文件，形如下图这样的结构

<img width="505" height="469" alt="object" src="https://github.com/user-attachments/assets/adb40405-0075-4d3a-8ade-0cd9aac1da7d" />

## 前提需求：

安装了isaacsim和isaaclab

## object.json转换为URDF并FIX

然后需要对object.json进行处理转换（在object.json中规定了关节的关系和位置角度等信息）。

然后再把其转换为urdf文件：调用的文件是**convert_object_json_to_urdf_pm.py**，和一个批量转换的脚本**run_conversion.py**。

随后需要对转换后的urdf文件进行检查，排除几何上的错误，这里运行的是**geom_fixing.py**文件。

## URDF转换为XML并FIX

把urdf再转换为XML文件，用的指令是

```bash
urdf2mjcf model.urdf model.xml.
```

urdf2mjcf来自仓库**WIKI-GRX-MJCF**。需要git clone下来：

```bash
git clone https://github.com/FFTAI/Wiki-GRx-MJCF.git
```

随后还需要把XML文件进行处理，把obj的绝对路径转化为相对路径，在此需要调用fix_xml.py文件。fixed的结果如下所示：

<img width="2112" height="815" alt="xml" src="https://github.com/user-attachments/assets/e91a3e69-3fb2-4690-85fb-fca8c0ab6429" />

注意进行转化需要在模型文件夹路径下面。

## XML转化为USDA文件

XML转化为USDA文件应当调用的是isaaclab的官方脚本，**convert_mjcf.py**，例如：

```bash
python ./convert_mjcf.py model_fixed.xml model.usda。
```

现在的USDA打开就是正常的了：

<img width="2478" height="1332" alt="usda" src="https://github.com/user-attachments/assets/96dc6251-fbac-4544-8007-37b2368f94ce" />
