import gi
gi.require_version("Gst", "1.0")
import math
import logging
from typing import Dict
import pyds
from gi.repository import GObject, Gst
from shapely.geometry import MultiLineString, Point

import utils



class Pipeline():
    def __init__(self, config: Dict, tiled_output_height: int, tiled_output_width: int) -> None:
        self.config = config
        self.tiled_output_height = tiled_output_height
        self.tiled_output_width = tiled_output_width
        self._build()
        self._model_config_path = "configs/model_config.txt"
        
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
        filter1 = Gst.ElementFactory.make("capsfilter", "filter1")
        if not filter1:
            raise RuntimeError("Unable to create the caps filter")
        
        filter1.set_property("caps", caps1)
        
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
        
        logging.info("Adding elements to Pipeline")
        self._pipeline.add(pgie)
        self._pipeline.add(nvvidconv1)
        self._pipeline.add(nvvidconv2)
        self._pipeline.add(filter1)
        self._pipeline.add(nvosd)
        self._pipeline.add(tiler)
        if utils.is_aarch64():
            self._pipeline.add(transform)
        self._pipeline.add(sink)
        
        logging.info("Linkink elements in the pipeline")
        streammux.link(pgie)
        pgie.link(nvvidconv1)
        nvvidconv1.link(filter1)
        filter1.link(tee)
        tee.link(queue1)
        tee.link(queue2)
        queue1.link(tiler)
        tiler.link(nvvidconv2)
        nvvidconv2.link(nvosd)
        queue2.link(nvmsgconv)
        nvmsgconv.link(nvmsgbroker)
        
        if utils.is_aarch64():
            nvosd.link(transform)
            transform.link(sink)
        else:
            nvosd.link(sink)
        
        self._loop = GObject.MainLoop()
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", bus_call, self._loop)
    
    
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
        
        
            
    
    def _osd_sink_buffer_probe(self, pad, info, u_data):
        pass