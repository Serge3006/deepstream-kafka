import pyds
import sys

MAX_TIME_STAMP_LEN = 32

# Callback function for deep-copying an NvDsEventMsgMeta struct
def meta_copy_func(data, user_data):
    # Cast data to pyds.NvDsUserMeta
    user_meta = pyds.NvDsUserMeta.cast(data)
    src_meta_data = user_meta.user_meta_data
    # Cast src_meta_data to pyds.NvDsEventMsgMeta
    srcmeta = pyds.NvDsEventMsgMeta.cast(src_meta_data)
    # Duplicate the memory contents of srcmeta to dstmeta
    # First use pyds.get_ptr() to get the C address of srcmeta, then
    # use pyds.memdup() to allocate dstmeta and copy srcmeta into it.
    # pyds.memdup returns C address of the allocated duplicate.
    dstmeta_ptr = pyds.memdup(pyds.get_ptr(srcmeta),
                              sys.getsizeof(pyds.NvDsEventMsgMeta))
    # Cast the duplicated memory to pyds.NvDsEventMsgMeta
    dstmeta = pyds.NvDsEventMsgMeta.cast(dstmeta_ptr)

    # Duplicate contents of ts field. Note that reading srcmeat.ts
    # returns its C address. This allows to memory operations to be
    # performed on it.
    dstmeta.ts = pyds.memdup(srcmeta.ts, MAX_TIME_STAMP_LEN + 1)

    # Copy the sensorStr. This field is a string property. The getter (read)
    # returns its C address. The setter (write) takes string as input,
    # allocates a string buffer and copies the input string into it.
    # pyds.get_string() takes C address of a string and returns the reference
    # to a string object and the assignment inside the binder copies content.
    dstmeta.sensorStr = pyds.get_string(srcmeta.sensorStr)

    if srcmeta.objSignature.size > 0:
        dstmeta.objSignature.signature = pyds.memdup(
            srcmeta.objSignature.signature, srcmeta.objSignature.size)
        dstmeta.objSignature.size = srcmeta.objSignature.size
        
    return dstmeta


# Callback function for freeing an NvDsEventMsgMeta instance
def meta_free_func(data, user_data):
    user_meta = pyds.NvDsUserMeta.cast(data)
    srcmeta = pyds.NvDsEventMsgMeta.cast(user_meta.user_meta_data)

    # pyds.free_buffer takes C address of a buffer and frees the memory
    # It's a NOP if the address is NULL
    pyds.free_buffer(srcmeta.ts)
    pyds.free_buffer(srcmeta.sensorStr)

    if srcmeta.objSignature.size > 0:
        pyds.free_buffer(srcmeta.objSignature.signature)
        srcmeta.objSignature.size = 0
        

def generate_event_msg_meta(obj_meta, frame_meta):
    msg_meta = pyds.alloc_nvds_event_msg_meta()
    msg_meta.bbox.top = obj_meta.rect_params.top
    msg_meta.bbox.left = obj_meta.rect_params.left
    msg_meta.bbox.width = obj_meta.rect_params.width
    msg_meta.bbox.height = obj_meta.rect_params.height
    msg_meta.frameId = frame_meta.frame_num
    msg_meta.trackingId = obj_meta.object_id
    msg_meta.confidence = obj_meta.confidence
    
    msg_meta.sensorId = 0
    msg_meta.placeId = 0
    msg_meta.moduleId = 0
    msg_meta.sensorStr = "sensor-0"
    
    msg_meta.ts = pyds.alloc_buffer(MAX_TIME_STAMP_LEN + 1)
    pyds.generate_ts_rfc3339(msg_meta.ts, MAX_TIME_STAMP_LEN)

    msg_meta.type = pyds.NvDsEventType.NVDS_EVENT_ENTRY
    msg_meta.objType = pyds.NvDsObjectType.NVDS_OBJECT_TYPE_PERSON
    msg_meta.objClassId = obj_meta.class_id
        
    return msg_meta