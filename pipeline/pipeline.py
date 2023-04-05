import gi
gi.require_version("Gst", "1.0")
import math
import logging
from typing import Dict
import pyds
from gi.repository import GObject, Gst
from shapely.geometry import MultiLineString, Point

import utils
from utils import  bus_call


class Pipeline():
    def __init__(self, config: Dict, protolib_path: str, connection_string: str) -> None:
        self.config = config
        self.tiled_output_height = 1080
        self.tiled_output_width = 1920
        self._model_config_path = "configs/model_config.txt"
        self._msg_config_path = "configs/msgconv_config.txt"
        self._protolib_path = protolib_path
        self._payload_type = 0
        self._connection_string = connection_string
        self._build()
        
    def _build(self) -> None:
        num_sources = len(self.config)
        
        # Initializing libraries
        GObject.threads_init()
        Gst.init(None)
        
        # creating deepstream elements
        logging.info("Creating pipeline")
        self._pipeline = Gst.Pipeline()
        is_live = False
        
        if not self._pipeline:
            raise RuntimeError("Unable to create pipeline")
        
        logging.info("Creating streammux module")
        streammux = Gst.ElementFactory.make("nvstreammux", "stream-muxer")
        if not streammux:
            raise RuntimeError("Unable to create streammux module")

        self._pipeline.add(streammux)
        
        for i in range(num_sources):
            logging.info(f"Creating source number {i}")
            uri = self.config[str(i)]["uri"]
            
            if "rtsp://" in uri or "http://" in uri:
                is_live = True
            
            source_bin = utils.create_source_bin(i, uri)
            self._pipeline.add(source_bin)
            sink_pad = streammux.get_request_pad(f"sink_{i}")
            if not sink_pad:
                raise RuntimeError("Unable to create streammux sink pad")
            source_pad = source_bin.get_static_pad("src")
            if not source_pad:
                raise RuntimeError("Unable to create source bin source pad")
            
            source_pad.link(sink_pad)
            
        logging.info("Creating inference module")
        pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
        if not pgie:
            raise RuntimeError("Unable to create inference module")
        
        logging.info("Creating video converter 1")
        nvvidconv1 = Gst.ElementFactory.make("nvvideoconvert", "convertor1")
        if not nvvidconv1:
            raise RuntimeError("Unable to create video converter module 1")
        
        logging.info("Creating filter 1")
        caps1 = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=RGBA")
        filter = Gst.ElementFactory.make("capsfilter", "filter1")
        if not filter:
            raise RuntimeError("Unable to create the caps filter")
        
        filter.set_property("caps", caps1)
        
        logging.info("Creating tiler")
        tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
        if not tiler:
            raise RuntimeError("Unable to create the tiler")

        logging.info("Creating video converter 2")
        nvvidconv2 = Gst.ElementFactory.make("nvvidconvert", "convertor2")
        if not nvvidconv2:
            raise RuntimeError("Unable to create video converter module 2")
        
        logging.info("Creating nvosd")
        nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
        if not nvosd:
            raise RuntimeError("Unable to create nvosd")
        
        logging.info("Creating tee")
        tee = Gst.ElementFactory.make("tee", "tee")
        if not tee:
            raise RuntimeError("Unable to create tee")
        
        logging.info("Creating queue")
        queue1 = Gst.ElementFactory.make("queue", "queue1")
        if not queue1:
            raise RuntimeError("Unable to create queue")
        
        logging.info("Creating queue")
        queue2 = Gst.ElementFactory.make("queue", "queue2")
        if not queue2:
            raise RuntimeError("Unable to create queue")
        
        logging.info("Creating nvmsgconv")
        nvmsgconv = Gst.ElementFactory.make("nvmsgconv", "msgconv")
        if not nvmsgconv:
            raise RuntimeError("Unable to create msgconv")
        
        logging.info("Creating nvmsgbroker")
        nvmsgbroker = Gst.ElementFactory.make("nvmsgbroker", "broker")
        if not nvmsgbroker:
            raise RuntimeError("Unable to create nvmsgbroker")
        
        if utils.is_aarch64():
            logging.info("Creating transform")
            transform = Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
            if not transform:
                raise RuntimeError("Unable to create transform")
        
        logging.info("Creating output sink")
        sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
        if not sink:
            raise RuntimeError("Unable to create output sink")
        
        if is_live:
            streammux.set_property("live-source", 1)
            
        streammux.set_property("width", 1920)
        streammux.set_property("height", 1080)
        streammux.set_property("batch_size", num_sources)
        streammux.set_property("batched-push-timeout", 40000)
        
        pgie.set_property("config-file-path", self._model_config_path)
        pgie_batch_size = pgie.get_property("batch_size")
        if pgie_batch_size != num_sources:
            logging.info(
                f"WARNING: Overriding infer-config batch size {pgie_batch_size} with "
                f"number of sources {num_sources}"
            )
            pgie.set_property("batch_size", num_sources)
            
        tiler_rows = int(math.sqrt(num_sources))
        tiler_columns = int(math.ceil(1.0 * num_sources / tiler_rows))
        tiler.set_property("rows", tiler_rows)
        tiler.set_property("columns", tiler_columns)
        tiler.set_property("width", self._tiled_output_width)
        tiler.set_property("height", self._tiled_output_height)
        
        sink.set_property("sync", 0)
        sink.set_property("qos", 0)
        
        nvmsgconv.set_property("config", self._msg_config_path)
        nvmsgconv.set_property("payload-type", self._payload_type)
        nvmsgbroker.set_property("proto-lib", self._protolib_path)
        nvmsgbroker.set_property("conn-str", self._connection_string)
        nvmsgbroker.set_property("sync", False)
        
        logging.info("Adding elements to Pipeline")
        self._pipeline.add(pgie)
        self._pipeline.add(nvvidconv1)
        self._pipeline.add(nvvidconv2)
        self._pipeline.add(filter)
        self._pipeline.add(tee)
        self._pipeline.add(nvmsgconv)
        self._pipeline.add(nvmsgbroker)
        self._pipeline.add(nvosd)
        self._pipeline.add(tiler)
        if utils.is_aarch64():
            self._pipeline.add(transform)
        self._pipeline.add(sink)
        
        logging.info("Linkink elements in the pipeline")
        streammux.link(pgie)
        pgie.link(nvvidconv1)
        nvvidconv1.link(filter)
        filter.link(tiler)
        tiler.link(nvvidconv2)
        nvvidconv2.link(nvosd)
        nvosd.link(tee)
        
        queue1.link(nvmsgconv)
        nvmsgconv.link(nvmsgbroker)
        
        if utils.is_aarch64():
            queue2.link(transform)
            transform.link(sink)
        else:
            nvosd.link(sink)
            
        queue1_sink_pad = queue1.get_static_pad("sink")
        queue2_sink_pad = queue2.get_static_pad("sink")
        tee_msg_pad = tee.get_request_pad("src_%u")
        tee_render_pad = tee.get_request_pad("src_%u")
        if not tee_msg_pad or not tee_render_pad:
            raise RuntimeError("Unable to get request pads\n")
        tee_msg_pad.link(queue1_sink_pad)
        tee_render_pad.link(queue2_sink_pad)
        
        # Create an event management loop
        self._loop = GObject.MainLoop()
        # Get bus in charge of communicating messages in the system
        bus = self._pipeline.get_bus()
        # Tell the bus to emit signal whenever it receives a new message
        bus.add_signal_watch()
        # Call the bus_call function whenever a message signal is received
        bus.connect("message", bus_call, self._loop)
        
        tee_sink_pad = tee.get_static_pad("sink")
        if not tee_sink_pad:
            raise RuntimeError("Unable to get tee sink")

        tee_sink_pad.add_probe(
            Gst.PadProbeType.BUFFER,
            self._tee_sink_buffer_probe,
            0
        )
    
    
    def _clean(self) -> None:
        logging.info("Cleaning up pipeline")
        pyds.unset_callback_funcs()
        self._pipeline.set_state(Gst.State.NULL)
    
    def run(self) -> None:
        logging.info("Running pipeline")
        self._pipeline.set_state(Gst.State.PLAYING)
        try:
            self._loop.run()
        except Exception as e:
            self._clean()
            raise e    
    
    def _tee_sink_buffer_probe(self, pad, info, u_data):
        gst_buffer = info.get_buffer()
        
        if not gst_buffer:
            logging.warning("Unable to get GstBuffer")
            
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list
        
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame)
            except StopIteration:
                break
            
            # Extracting the configuration for the current frame
            source_id = frame_meta.source_id
            stream_config = self.config[str(source_id)]
            restricted_zones = stream_config["restricted_zones"]
            
            # Display the restricted zones
            for zone in restricted_zones:
                display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
                display_meta.num_lines = len(zone)
                lines_params = display_meta.line_params
                for line_idx in range(display_meta.num_lines):
                    params = lines_params[line_idx]
                    line = zone[line_idx]
                    
                    params.x1 = line[0][0]
                    params.x1 = line[0][1]
                    params.x2 = line[1][0]
                    params.y2 = line[1][1]
                    
                    params.line_width = 3
                    params.line_color.set(1.0, 0, 0, 1.0)
                    
                pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
            
            l_obj = frame_meta.obj_meta_list
            
            while l_obj is not None:
                try:
                    obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                except StopIteration:
                    break
                
                # Making all the boxes green
                obj_meta.rect_params.border_color.set(0, 1.0, 1.0)
                
                # Only high confidence detections are evaluated
                if obj_meta.class_id == 2 and obj_meta.confidence >= stream_config["confidence"]:
                    feet_point_x = obj_meta.rect_params.left + obj_meta.rect_params.width / 2
                    feet_point_y = obj_meta.rect_params.top + obj_meta.rect_params.height
                    person_position = Point(feet_point_x, feet_point_y)
                    
                    for zone in enumerate(restricted_zones):
                        # Create polygons from lines, used to evaliated persons positions
                        zone = MultiLineString(zone).convex_hull
                        alarm = zone.contains(person_position)
                        if alarm:
                            obj_meta.rect_params.border_color.set(1.0, 0, 0, 1.0)
                        else:
                            break
                        
            try:
                l_obj = l_obj.next
            except StopIteration:
                break
            
        return Gst.PadProbeReturn.OK
    