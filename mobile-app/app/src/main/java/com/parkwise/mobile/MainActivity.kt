package com.parkwise.mobile

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceError
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.ComponentActivity

class MainActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var errorView: TextView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this).apply {
            setBackgroundColor(Color.WHITE)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = false

                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) showConnectionError()
                }
            }
        }

        errorView = TextView(this).apply {
            setBackgroundColor(Color.WHITE)
            setTextColor(Color.rgb(16, 36, 28))
            textSize = 16f
            setPadding(48, 96, 48, 48)
            text = "Unable to open Parkwise.\n\nStart the local backend with:\npython run_mobile_backend.py\n\nTap here to retry."
            setOnClickListener { loadParkwise() }
            visibility = TextView.GONE
        }

        setContentView(FrameLayout(this).apply {
            addView(webView, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            addView(errorView, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        })

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
        loadParkwise()
    }

    private fun loadParkwise() {
        errorView.visibility = TextView.GONE
        webView.visibility = WebView.VISIBLE
        webView.loadUrl(BuildConfig.WEB_APP_URL)
    }

    private fun showConnectionError() {
        webView.visibility = WebView.GONE
        errorView.visibility = TextView.VISIBLE
    }
}
