package com.bm85.tvremote.proto

import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.io.InputStream
import java.io.OutputStream

/** Minimal protobuf encoder (varint + length-delimited fields only). */
class ProtoWriter {
    private val out = ByteArrayOutputStream()

    private fun varint(value: Long) {
        var x = value
        while (true) {
            if (x and 0x7FL.inv() == 0L) {
                out.write(x.toInt())
                return
            }
            out.write(((x and 0x7FL) or 0x80L).toInt())
            x = x ushr 7
        }
    }

    private fun tag(field: Int, wireType: Int) = varint(((field shl 3) or wireType).toLong())

    fun int(field: Int, value: Long): ProtoWriter {
        tag(field, 0); varint(value); return this
    }

    fun int(field: Int, value: Int): ProtoWriter = int(field, value.toLong())

    fun bool(field: Int, value: Boolean): ProtoWriter = int(field, if (value) 1L else 0L)

    fun bytes(field: Int, value: ByteArray): ProtoWriter {
        tag(field, 2); varint(value.size.toLong()); out.write(value); return this
    }

    fun string(field: Int, value: String): ProtoWriter = bytes(field, value.toByteArray(Charsets.UTF_8))

    fun message(field: Int, value: ProtoWriter): ProtoWriter = bytes(field, value.toByteArray())

    fun toByteArray(): ByteArray = out.toByteArray()
}

/** Minimal protobuf decoder: field number -> list of raw values (Long for varints, ByteArray for length-delimited). */
class ProtoMessage(bytes: ByteArray) {
    private val fields = HashMap<Int, MutableList<Any>>()

    init {
        var pos = 0
        fun readVarint(): Long {
            var result = 0L
            var shift = 0
            while (true) {
                if (pos >= bytes.size) throw IllegalArgumentException("Truncated varint")
                val b = bytes[pos++].toInt() and 0xFF
                result = result or ((b and 0x7F).toLong() shl shift)
                if (b and 0x80 == 0) return result
                shift += 7
                if (shift > 63) throw IllegalArgumentException("Varint too long")
            }
        }
        while (pos < bytes.size) {
            val key = readVarint()
            val field = (key ushr 3).toInt()
            val value: Any = when ((key and 7L).toInt()) {
                0 -> readVarint()
                1 -> { pos += 8; 0L }
                2 -> {
                    val len = readVarint().toInt()
                    if (len < 0 || pos + len > bytes.size) throw IllegalArgumentException("Truncated field")
                    val v = bytes.copyOfRange(pos, pos + len)
                    pos += len
                    v
                }
                5 -> { pos += 4; 0L }
                else -> throw IllegalArgumentException("Unsupported wire type")
            }
            fields.getOrPut(field) { mutableListOf() }.add(value)
        }
    }

    fun has(field: Int): Boolean = fields.containsKey(field)

    fun long(field: Int): Long = fields[field]?.firstOrNull() as? Long ?: 0L

    fun int(field: Int): Int = long(field).toInt()

    fun bool(field: Int): Boolean = long(field) != 0L

    fun bytes(field: Int): ByteArray? = fields[field]?.firstOrNull() as? ByteArray

    fun string(field: Int): String? = bytes(field)?.toString(Charsets.UTF_8)

    fun message(field: Int): ProtoMessage? = bytes(field)?.let { ProtoMessage(it) }
}

/** Messages on the wire are prefixed with their length as a varint. */
object Framing {
    fun write(out: OutputStream, msg: ByteArray) {
        val buf = ByteArrayOutputStream(msg.size + 5)
        var x = msg.size
        while (x >= 0x80) {
            buf.write((x and 0x7F) or 0x80)
            x = x ushr 7
        }
        buf.write(x)
        buf.write(msg)
        out.write(buf.toByteArray()) // single write = single TLS record
        out.flush()
    }

    fun read(input: InputStream): ByteArray {
        var len = 0
        var shift = 0
        while (true) {
            val b = input.read()
            if (b < 0) throw EOFException("Connection closed by TV")
            len = len or ((b and 0x7F) shl shift)
            if (b and 0x80 == 0) break
            shift += 7
            if (shift > 28) throw IllegalArgumentException("Bad length")
        }
        val buf = ByteArray(len)
        var off = 0
        while (off < len) {
            val n = input.read(buf, off, len - off)
            if (n < 0) throw EOFException("Connection closed by TV")
            off += n
        }
        return buf
    }
}
