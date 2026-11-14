package com.bm85.tvremote.atv

import android.content.Context
import org.bouncycastle.asn1.x500.X500Name
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder
import java.io.File
import java.math.BigInteger
import java.net.Socket
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Principal
import java.security.PrivateKey
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.Date
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLEngine
import javax.net.ssl.X509ExtendedKeyManager
import javax.net.ssl.X509TrustManager

/**
 * Holds this phone's self-signed client certificate. The TV remembers the certificate after pairing,
 * so it is created once and kept in the app's private storage.
 */
class CertManager(context: Context) {
    private val file = File(context.filesDir, "atv_client.p12")
    private val password = "atvremote".toCharArray()
    private val alias = "atvremote"
    private var keyStore: KeyStore? = null

    @Synchronized
    private fun store(): KeyStore {
        keyStore?.let { return it }
        val ks = KeyStore.getInstance("PKCS12")
        var loaded = false
        if (file.exists()) {
            try {
                file.inputStream().use { ks.load(it, password) }
                loaded = ks.containsAlias(alias)
            } catch (_: Exception) {
                loaded = false
            }
        }
        if (!loaded) {
            ks.load(null, null)
            generate(ks)
            file.outputStream().use { ks.store(it, password) }
        }
        keyStore = ks
        return ks
    }

    private fun generate(ks: KeyStore) {
        val kpg = KeyPairGenerator.getInstance("RSA")
        kpg.initialize(2048)
        val kp = kpg.generateKeyPair()
        val name = X500Name("CN=atvremote, O=TVRemote")
        val now = System.currentTimeMillis()
        val builder = JcaX509v3CertificateBuilder(
            name, BigInteger.valueOf(now), Date(now - 86_400_000L),
            Date(now + 3650L * 86_400_000L), name, kp.public
        )
        val signer = JcaContentSignerBuilder("SHA256withRSA").build(kp.private)
        val cert = JcaX509CertificateConverter().getCertificate(builder.build(signer))
        ks.setKeyEntry(alias, kp.private, password, arrayOf(cert))
    }

    fun certificate(): X509Certificate = store().getCertificate(alias) as X509Certificate

    private fun privateKey(): PrivateKey = store().getKey(alias, password) as PrivateKey

    fun sslContext(): SSLContext {
        val cert = certificate()
        val key = privateKey()
        // Always present our certificate, whatever CA list the TV advertises.
        val keyManager = object : X509ExtendedKeyManager() {
            override fun getClientAliases(keyType: String?, issuers: Array<out Principal>?): Array<String> = arrayOf(alias)
            override fun chooseClientAlias(keyType: Array<out String>?, issuers: Array<out Principal>?, socket: Socket?): String = alias
            override fun chooseEngineClientAlias(keyType: Array<out String>?, issuers: Array<out Principal>?, engine: SSLEngine?): String = alias
            override fun getServerAliases(keyType: String?, issuers: Array<out Principal>?): Array<String>? = null
            override fun chooseServerAlias(keyType: String?, issuers: Array<out Principal>?, socket: Socket?): String? = null
            override fun getCertificateChain(a: String?): Array<X509Certificate> = arrayOf(cert)
            override fun getPrivateKey(a: String?): PrivateKey = key
        }
        // TVs use self-signed certificates: accept them (local network only).
        val trustAll = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        val ctx = SSLContext.getInstance("TLS")
        ctx.init(arrayOf(keyManager), arrayOf(trustAll), SecureRandom())
        return ctx
    }
}
