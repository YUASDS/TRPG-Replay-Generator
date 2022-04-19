#!/usr/bin/env python
# coding: utf-8
import sys
import os
import pygame
import pygame.freetype
import time  # 开发模式，显示渲染帧率
from loguru import logger
from golables_config import (
    python3,
    args,
    render_arg,
    stdin_text,
    object_define_text,
    charactor_table,
)
from func import pause_SE, render, stop_SE, media_list, instantiate_object, Parser
from media_class import Background

# from myclass import Background, Text, StrokeText, Bubble, Animation, BGM, Audio


edtion = "alpha 1.8.5"
# # 参数处理
# ap = argparse.ArgumentParser(description="Generating your TRPG replay video from logfile.")
# ap.add_argument("-l", "--LogFile", help='The standerd input of this programme, which is mainly composed of TRPG log.',type=str)
# ap.add_argument("-d", "--MediaObjDefine", help='Definition of the media elements, using real python code.',type=str)
# ap.add_argument("-t", "--CharacterTable", help='The correspondence between character and media elements, using tab separated text file or Excel table.',type=str)
# ap.add_argument("-o", "--OutputPath", help='Choose the destination directory to save the project timeline and breakpoint file.',type=str,default=None)
# # 选项
# ap.add_argument("-F", "--FramePerSecond", help='Set the FPS of display, default is 30 fps, larger than this may cause lag.',type=int,default=30)
# ap.add_argument("-W", "--Width", help='Set the resolution of display, default is 1920, larger than this may cause lag.',type=int,default=1920)
# ap.add_argument("-H", "--Height", help='Set the resolution of display, default is 1080, larger than this may cause lag.',type=int,default=1080)
# ap.add_argument("-Z", "--Zorder", help='Set the display order of layers, not recommended to change the values unless necessary!',type=str,
#                 default='BG3,BG2,BG1,Am3,Am2,Am1,Bb')
# # 用于语音合成的key
# ap.add_argument("-K", "--AccessKey", help='Your AccessKey, to use with --SynthsisAnyway',type=str,default="Your_AccessKey")
# ap.add_argument("-S", "--AccessKeySecret", help='Your AccessKeySecret, to use with --SynthsisAnyway',type=str,default="Your_AccessKey_Secret")
# ap.add_argument("-A", "--Appkey", help='Your Appkey, to use with --SynthsisAnyway',type=str,default="Your_Appkey")
# # 用于导出视频的质量值
# ap.add_argument("-Q", "--Quality", help='Choose the quality (ffmpeg crf) of output video, to use with --ExportVideo.',type=int,default=24)
# # Flags
# ap.add_argument('--ExportXML',help='Export a xml file to load in Premiere Pro, some .png file will be created at same time.',action='store_true')
# ap.add_argument('--ExportVideo',help='Export MP4 video file, this will disables interface display',action='store_true')
# ap.add_argument('--SynthesisAnyway',help='Execute speech_synthezier first, and process all unprocessed asterisk time label.',action='store_true')
# ap.add_argument('--FixScreenZoom',help='Windows system only, use this flag to fix incorrect windows zoom.',action='store_true')

# args = ap.parse_args()

# 退出程序


def system_terminated(exit_type="Error"):
    exit_print = {
        "Error": "A major error occurred. Execution terminated!",
        "User": "Display terminated, due to user commands.",
        "Video": "Video exported. Execution terminated!",
        "End": "Display finished!",
    }
    print(f"[replay generator]: {exit_print[exit_type]}")
    sys.exit()


media_obj = args.MediaObjDefine  # 媒体对象定义文件的路径
char_tab = args.CharacterTable  # 角色和媒体对象的对应关系文件的路径
stdin_log = args.LogFile  # log路径
output_path = args.OutputPath  # 保存的时间轴，断点文件的目录

screen_size = (args.Width, args.Height)  # 显示的分辨率
frame_rate = args.FramePerSecond  # 帧率 单位fps
zorder = args.Zorder.split(",")  # 渲染图层顺序

AKID = args.AccessKey
AKKEY = args.AccessKeySecret
APPKEY = args.Appkey

crf = args.Quality  # 导出视频的质量值

exportXML = args.ExportXML  # 导出为XML
exportVideo = args.ExportVideo  # 导出为视频
synthfirst = args.SynthesisAnyway  # 是否先行执行语音合成
fixscreen = args.FixScreenZoom  # 是否修复窗体缩放


# Main():

print("[replay generator]: Welcome to use TRPG-replay-generator " + edtion)

# 初始化界面

if fixscreen:
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()  # 修复错误的缩放，尤其是在移动设备。
    except Exception:
        print(
            "->[33m[warning]:->[0m OS exception, --FixScreenZoom is only avaliable on windows system!"
        )

pygame.init()
pygame.display.set_caption("TRPG Replay Generator " + edtion)
fps_clock = pygame.time.Clock()
screen = pygame.display.set_mode(screen_size)
note_text = pygame.freetype.Font("./media/SourceHanSansCN-Regular.otf")  # type: ignore

# 建立音频轨道
VOICE = pygame.mixer.Channel(1)
SOUEFF = pygame.mixer.Channel(2)
channel_list = {"Voice": VOICE, "SE": SOUEFF}

# black = Background("black")
# white = Background("white")
# media_list.extend(("black", "white"))
# 转换媒体对象


media_list = instantiate_object(object_define_text)

par_obj = Parser(stdin_text, render_arg, charactor_table=charactor_table)

render_timeline, break_point, bulitin_media = par_obj.parser()


# 检查是否需要先做语音合成

if synthfirst:
    command = (
        python3
        + " ./speech_synthesizer.py --LogFile {lg} --MediaObjDefine {md} --CharacterTable {ct} --OutputPath {of} --AccessKey {AK} --AccessKeySecret {AS} --Appkey {AP}"
    )
    command = command.format(
        lg=stdin_log.replace("\\", "/"),
        md=media_obj.replace("\\", "/"),
        of=output_path,
        ct=char_tab.replace("\\", "/"),
        AK=AKID,
        AS=AKKEY,
        AP=APPKEY,
    )
    print(
        "[replay generator]: Flag --SynthesisAnyway detected, running command:\n"
        + "->[32m"
        + command
        + "->[0m"
    )
    try:
        os.system(command)
        # 将当前的标准输入调整为处理后的log文件
        if os.path.isfile(output_path + "/AsteriskMarkedLogFile.txt"):
            stdin_log = output_path + "/AsteriskMarkedLogFile.txt"
        else:
            raise OSError("Exception above")
        #
    except Exception as E:
        logger.exception(
            "[replay generator]: Failed to run speech_synthesizer.py, please check the log file."
        )

        print("->[33m[warning]:->[0m Failed to synthesis speech, due to:", E)


# 判断是否指定输出路径，准备各种输出选项
if output_path is not None:
    print(
        "[replay generator]: The timeline and breakpoint file will be save at "
        + output_path
    )
    timenow = "%d" % time.time()
    render_timeline.to_pickle(output_path + "/" + timenow + ".timeline")
    break_point.to_pickle(output_path + "/" + timenow + ".breakpoint")
    bulitin_media.to_pickle(output_path + "/" + timenow + ".bulitinmedia")
    if exportXML:
        command = (
            python3
            + " ./export_xml.py --TimeLine {tm} --MediaObjDefine {md} --OutputPath {of} --FramePerSecond {fps} --Width {wd} --Height {he} --Zorder {zd}"
        )
        command = command.format(
            tm=output_path + "/" + timenow + ".timeline",
            md=media_obj.replace("\\", "/"),
            of=output_path.replace("\\", "/"),
            fps=frame_rate,
            wd=screen_size[0],
            he=screen_size[1],
            zd=",".join(zorder),
        )
        print(
            "[replay generator]: Flag --ExportXML detected, running command:\n"
            + "->[32m"
            + command
            + "->[0m"
        )
        try:
            os.system(command)
        except Exception as E:
            logger.exception("Failed to export XML, due to:", E)
            print("->[33m[warning]:->[0m Failed to export XML, due to:", E)
    if exportVideo:
        command = (
            python3
            + " ./export_video.py --TimeLine {tm} --MediaObjDefine {md} --OutputPath {of} --FramePerSecond {fps} --Width {wd} --Height {he} --Zorder {zd} --Quality {ql}"
        )
        command = command.format(
            tm=output_path + "/" + timenow + ".timeline",
            md=media_obj.replace("\\", "/"),
            of=output_path.replace("\\", "/"),
            fps=frame_rate,
            wd=screen_size[0],
            he=screen_size[1],
            zd=",".join(zorder),
            ql=crf,
        )
        print(
            "[replay generator]: Flag --ExportVideo detected, running command:\n"
            + "->[32m"
            + command
            + "->[0m"
        )
        try:
            os.system(command)
        except Exception as E:
            logger.exception("Failed to export video, due to:", E)
            print("->[33m[warning]:->[0m Failed to export Video, due to:", E)
        system_terminated("Video")  # 如果导出为视频，则提前终止程序


# 预备画面
white = Background("white")
W, H = screen_size
white.display(screen)
screen.blit(
    pygame.transform.scale(
        pygame.image.load(os.path.join("media", "sorc.jpg")), (H // 5, H // 5)
    ),
    (0.01 * H, 0.79 * H),
)
screen.blit(
    note_text.render(
        "Welcome to TRPG Replay Generator!",
        fgcolor=(150, 150, 150, 255),
        size=0.0315 * W,
    )[0],
    (0.230 * W, 0.460 * H),
)  # for 1080p
screen.blit(
    note_text.render(edtion, fgcolor=(150, 150, 150, 255), size=0.0278 * H)[0],
    (0.900 * W, 0.963 * H),
)
screen.blit(
    note_text.render(
        "Press space to begin.", fgcolor=(150, 150, 150, 255), size=0.0278 * H
    )[0],
    (0.417 * W, 0.926 * H),
)
pygame.display.update()
begin = True
while begin is False:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            system_terminated("User")
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.time.delay(1000)
                pygame.quit()
                system_terminated("User")
            elif event.key == pygame.K_SPACE:
                begin = True
                break
#


try:
    # 主循环
    n = 0
    forward = 1  # forward==0代表暂停
    while n < break_point.max():
        ct = time.time()
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    system_terminated("User")
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        stop_SE(channel_list)
                        pygame.time.delay(1000)
                        pygame.quit()
                        system_terminated("User")
                    elif event.key == pygame.K_a:
                        n = break_point[(break_point - n) < 0].max()
                        n = break_point[(break_point - n) < 0].max()
                        if n != n:  # 确保不会被a搞崩
                            n = 0
                        stop_SE(channel_list)
                        continue
                    elif event.key == pygame.K_d:
                        n = break_point[(break_point - n) > 0].min()
                        stop_SE(channel_list)
                        continue
                    elif event.key == pygame.K_SPACE:  # 暂停
                        forward = 1 - forward  # 1->0 0->1
                        pause_SE(forward, channel_list)  # 0:pause,1:unpause

            if n in render_timeline.index:
                this_frame = render_timeline.loc[n]
                # screen.fill((0, 0, 0))
                render(this_frame, channel_list, media_list, screen)
                # logger.info(this_frame)
                if forward == 1:
                    screen.blit(
                        note_text.render(
                            "%d" % (1 // (time.time() - ct + 1e-4)),
                            fgcolor=(100, 255, 100, 255),
                            size=0.0278 * H,
                        )[0],
                        (10, 10),
                    )  # render rate +1e-4 to avoid float divmod()
                else:
                    screen.blit(
                        note_text.render(
                            "Press space to continue.",
                            fgcolor=(100, 255, 100, 255),
                            size=0.0278 * H,
                        )[0],
                        (0.410 * W, 0.926 * H),
                    )  # pause
            else:
                pass  # 节约算力
            pygame.display.flip()
            n = n + forward  # 下一帧
            fps_clock.tick(frame_rate)
        except RuntimeError as E:
            logger.exception("Exception")
            print(E)
            print("->[31m[RenderError]:->[0m", "Render exception at frame:", n)
            pygame.quit()
            system_terminated("Error")
    pygame.quit()
    system_terminated("End")
except Exception:
    logger.exception("Exception")
