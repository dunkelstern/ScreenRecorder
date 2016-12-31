import argparse
import os, subprocess
import platform

# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')
gi.require_version('GstNet', '1.0')
gi.require_version('GstRtsp', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject, GstNet, GstRtsp, GLib


if platform.system() == 'Linux':
    available_encoders = [
        'x264',   # Uses libx264 'veryfast' preset, needs much CPU power
        'vaapi',  # Intel CPU driver (only when running Xorg on Intel or Glamour drivers
        'nvenc',  # NVidia encoder, needs GTX680 or higher (GK104/Keppler or higher) and ffmpeg with support compiled in
        # TODO: What about AMD graphics card acceleration?
    ]
elif platform.system() == 'Darwin':
    available_encoders = [
        'vtenc_h264',
        'vtenc_h264_hw'
    ]
elif platform.system() == 'Windows':
    available_encoders = [
        'openh264',
        'x264'
    ]

encoder_delay = {
    'x264': 1150,
    'vaapi': 240,
    'nvenc': 1000/25,
    'vtenc_h264': 0,
    'vtenc_h264_hw': 0,
    'openh264': 0
}

def get_recording_sink(**kwargs):
        # read settings
        from ScreenRec.model.configfile import config
        
        scale_width = kwargs.get('scale_width', config.rec_settings.scale_width)
        scale_height = kwargs.get('scale_height', config.rec_settings.scale_height)
        if scale_width == 0:
            scale_width = config.rec_settings.width
        if scale_height == 0:
            scale_height = config.rec_settings.height
        encoder = kwargs.get('encoder', config.rec_settings.encoder)
        if not encoder:
            encoder = ScreenRecorder.ENCODERS[0]
        port = kwargs.get('port', None)
        fps = kwargs.get('fps', config.rec_settings.fps)

        print('Using {} encoder'.format(encoder))

        # create encoder bin
        enc = Gst.Bin.new('encoder')

        queue = Gst.ElementFactory.make('queue')
        queue.set_property('max-size-buffers', 200)
        queue.set_property('max-size-bytes', 104857600)  # 10 MB
        queue.set_property('max-size-time', 10000000000)  # 10 sec
        
        videorate = Gst.ElementFactory.make('videorate')
        cap_string = 'video/x-raw,framerate={}/1'.format(fps)
        filter = Gst.ElementFactory.make('capsfilter')
        caps = Gst.Caps.from_string(cap_string)

        enc.add(queue)
        enc.add(videorate)
        queue.link(videorate)

        # build encoding pipelines
        src = None
        sink = None
        if encoder == 'vaapi':
            # scale, convert and encode with hardware acceleration
            scaler = Gst.ElementFactory.make('vaapipostproc')
            scaler.set_property('width', scale_width)
            scaler.set_property('height', scale_height)
            scaler.set_property('scale-method', 2)
            enc.add(scaler)

            video_encoder = Gst.ElementFactory.make('vaapih264enc')
            video_encoder.set_property('keyframe-period', fps)
            enc.add(video_encoder)

            scaler.link(video_encoder)
            src = scaler
            sink = video_encoder
        elif encoder == 'x264':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            enc.add(convert)

            scaler = Gst.ElementFactory.make('videoscale')
            enc.add(scaler)
            cap_string = 'video/x-raw,width={},height={}'.format(
                scale_width, scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)
            enc.add(filter)

            video_encoder = Gst.ElementFactory.make('x264enc')
            video_encoder.set_property('speed-preset', 'veryfast')
            #video_encoder.set_property('tune', 4)  # zero latency
            enc.add(video_encoder)

            convert.link(scaler)
            scaler.link(filter)
            filter.link(video_encoder)

            src = convert
            sink = video_encoder
        elif encoding_method == 'openh264':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            enc.add(convert)

            scaler = Gst.ElementFactory.make('videoscale')
            enc.add(scaler)
            cap_string = 'video/x-raw,width={},height={}'.format(
                scale_width, scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)
            enc.add(filter)

            video_encoder = Gst.ElementFactory.make('openh264enc')
            video_encoder.set_property('complexity', 0)

            enc.add(video_encoder)

            convert.link(scaler)
            scaler.link(filter)
            filter.link(video_encoder)

            src = convert
            sink = video_encoder
        elif encoding_method == 'vtenc_h264' or encoding_method == 'vtenc_h264_hw':
            # scale, convert and encode with software encoders

            convert = Gst.ElementFactory.make('autovideoconvert')
            enc.add(convert)

            scaler = Gst.ElementFactory.make('videoscale')
            enc.add(scaler)
            cap_string = 'video/x-raw,width={},height={}'.format(
                scale_width, scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)
            enc.add(filter)

            video_encoder = Gst.ElementFactory.make(encoding_method)

            enc.add(video_encoder)

            convert.link(scaler)
            scaler.link(filter)
            filter.link(video_encoder)

            src = convert
            sink = video_encoder

        videorate.link(src)

        # output part of pipeline
        out_queue = Gst.ElementFactory.make('queue')
        enc.add(out_queue)
        sink.link(out_queue)

        parser = Gst.ElementFactory.make('h264parse')
        enc.add(parser)
        out_queue.link(parser)

        filesink = None
        if port:
            rtp_payload = Gst.ElementFactory.make('rtph264pay')
            rtp_payload.set_property('config-interval', -1)  # send sps and pps with every keyframe
            enc.add(rtp_payload)

            udpsink = Gst.ElementFactory.make('udpsink')
            udpsink.set_property('sync', True)
            udpsink.set_property('host', '127.0.0.1')
            udpsink.set_property('port', port)
            enc.add(udpsink)

            parser.link(rtp_payload)
            rtp_payload.link(udpsink)
        else:
            muxer = Gst.ElementFactory.make('mpegtsmux')
            enc.add(muxer)
            parser.link(muxer)
            filesink = Gst.ElementFactory.make('filesink')
            enc.add(filesink)
            muxer.link(filesink)

        ghost_sink = Gst.GhostPad.new('sink', queue.get_static_pad('sink'))
        enc.add_pad(ghost_sink)

        return enc, filesink

# def build_nvenc_pipeline(self, src):
#     # scale and convert with software encoders, send rtp stream to ffmpeg for encoding
#     convert = Gst.ElementFactory.make('autovideoconvert')
#     self.pipeline.add(convert)
#     src.link(convert)

#     self.sink = Gst.ElementFactory.make('fdsink')

#     encoder = Gst.ElementFactory.make('y4menc')

#     if self.scale_width and self.scale_height:
#         scaler = Gst.ElementFactory.make('videoscale')
#         cap_string = 'video/x-raw,width={},height={}'.format(
#             self.scale_width, self.scale_height
#         )
#         caps = Gst.Caps.from_string(cap_string)
#         filter = Gst.ElementFactory.make('capsfilter')
#         filter.set_property('caps', caps)

#         self.pipeline.add(scaler)
#         self.pipeline.add(filter)
#         self.pipeline.add(encoder)
#         convert.link(scaler)
#         scaler.link(filter)
#         filter.link(encoder)
#     else:
#         self.pipeline.add(encoder)
#         convert.link(encoder)

#     # add sink
#     self.pipeline.add(self.sink)

#     # link encoder to sink
#     encoder.link(self.sink)

#     self.create_bus()

