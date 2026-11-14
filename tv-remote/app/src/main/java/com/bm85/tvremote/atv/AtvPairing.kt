package com.bm85.tvremote.atv

import com.bm85.tvremote.proto.Framing
import com.bm85.tvremote.proto.ProtoMessage
import com.bm85.tvremote.proto.ProtoWriter
import java.io.Closeable
import java.math.BigInteger
import java.net.InetSocketAddress
import java.security.MessageDigest
import java.security.cert.X509Certificate
import java.security.interfaces.RSAPublicKey
import javax.net.ssl.SSLSocket

class PairingException(message: String, val retryable: Boolean = false) : Exception(message)

/**
 * Android TV Remote v2 pairing ("Polo" protocol, TCP 6467).
 * [start] makes the TV display a 6-character code; [finish] sends the proof built from that code.
 * Blocking calls: run off the main thread.
 */
class AtvPairing(
    private val host: String,
    private val certs: CertManager,
    private val clientName: String,
) : Closeable {
    private var socket: SSLSocket? = null

    fun start() {
        val s = certs.sslContext().socketFactory.createSocket() as SSLSocket
        try {
            s.connect(InetSocketAddress(host, PORT), 5000)
            s.soTimeout = 15000
            s.startHandshake()
        } catch (e: Exception) {
            try { s.close() } catch (_: Exception) {}
            throw PairingException("Cannot reach the TV on port $PORT (${e.message}). Check the IP and that the TV is on.")
        }
        socket = s
        // PairingRequest(service_name=1, client_name=2)
        exchange(10, ProtoWriter().string(1, "atvremote").string(2, clientName), 11)
        // PairingOption(input_encodings=[HEXADECIMAL x6], preferred_role=INPUT)
        exchange(20, ProtoWriter().message(1, encoding()).int(3, ROLE_INPUT), 20)
        // PairingConfiguration(encoding, client_role=INPUT) -> TV shows the code
        exchange(30, ProtoWriter().message(1, encoding()).int(2, ROLE_INPUT), 31)
    }

    fun finish(rawCode: String) {
        val code = rawCode.trim().uppercase()
        if (code.length != 6 || !code.all { it in "0123456789ABCDEF" }) {
            throw PairingException("The code has 6 characters (0-9, A-F).", retryable = true)
        }
        val s = socket ?: throw PairingException("Pairing not started")
        val client = certs.certificate().publicKey as RSAPublicKey
        val server = (s.session.peerCertificates[0] as X509Certificate).publicKey as RSAPublicKey
        val md = MessageDigest.getInstance("SHA-256")
        md.update(unsigned(client.modulus))
        md.update(unsigned(client.publicExponent))
        md.update(unsigned(server.modulus))
        md.update(unsigned(server.publicExponent))
        md.update(hex(code.substring(2)))
        val hash = md.digest()
        if ((hash[0].toInt() and 0xFF) != code.substring(0, 2).toInt(16)) {
            throw PairingException("Wrong code, check the TV screen and retry.", retryable = true)
        }
        exchange(40, ProtoWriter().bytes(1, hash), 41)
    }

    private fun encoding() = ProtoWriter().int(1, ENCODING_HEX).int(2, 6)

    private fun exchange(field: Int, inner: ProtoWriter, expected: Int): ProtoMessage {
        val s = socket ?: throw PairingException("Not connected")
        val msg = ProtoWriter().int(1, 2).int(2, 200).message(field, inner).toByteArray()
        Framing.write(s.outputStream, msg)
        val resp = ProtoMessage(Framing.read(s.inputStream))
        val status = resp.int(2)
        if (status != 200) {
            throw PairingException(
                when (status) {
                    402 -> "The TV rejected the code."
                    401 -> "The TV rejected the pairing configuration."
                    else -> "The TV answered with error $status."
                }
            )
        }
        if (!resp.has(expected)) throw PairingException("Unexpected answer from the TV.")
        return resp
    }

    override fun close() {
        val s = socket ?: return
        socket = null
        try { s.close() } catch (_: Exception) {}
    }

    companion object {
        const val PORT = 6467
        private const val ENCODING_HEX = 3
        private const val ROLE_INPUT = 1

        private fun unsigned(x: BigInteger): ByteArray {
            val b = x.toByteArray()
            return if (b.size > 1 && b[0] == 0.toByte()) b.copyOfRange(1, b.size) else b
        }

        private fun hex(s: String): ByteArray = ByteArray(s.length / 2) { i ->
            s.substring(i * 2, i * 2 + 2).toInt(16).toByte()
        }
    }
}
