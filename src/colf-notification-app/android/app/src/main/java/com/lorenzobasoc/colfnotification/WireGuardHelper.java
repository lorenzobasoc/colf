package com.lorenzobasoc.colfnotification;

import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class WireGuardHelper {

    private static final String TAG = "WireGuardHelper";
    // WireGuard Intent Actions
    private static final String ACTION_SET_TUNNEL_UP = "com.wireguard.android.action.SET_TUNNEL_UP";
    private static final String ACTION_SET_TUNNEL_DOWN = "com.wireguard.android.action.SET_TUNNEL_DOWN";
    private static final String EXTRA_TUNNEL = "tunnel";
    
    // Tunnel Name to activate
    private static final String TUNNEL_NAME = "develop";

    public static void connect(Context context) {
        Log.d(TAG, "Attempting to enable WireGuard tunnel: " + TUNNEL_NAME);
        Intent intent = new Intent(ACTION_SET_TUNNEL_UP);
        intent.setPackage("com.wireguard.android");
        intent.putExtra(EXTRA_TUNNEL, TUNNEL_NAME);
        context.sendBroadcast(intent);
    }
    
    public static void disconnect(Context context) {
        Log.d(TAG, "Attempting to disable WireGuard tunnel: " + TUNNEL_NAME);
        Intent intent = new Intent(ACTION_SET_TUNNEL_DOWN);
        intent.setPackage("com.wireguard.android");
        intent.putExtra(EXTRA_TUNNEL, TUNNEL_NAME);
        context.sendBroadcast(intent);
    }
}
