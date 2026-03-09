package com.lorenzobasoc.colfnotification;

import android.util.Log;
import java.io.IOException;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class NetworkHelper {
    private static final String TAG = "NetworkHelper";
    // REPLACE WITH YOUR RASPBERRY PI IP ADDRESS
    // For now assuming a local DNS or static IP
    private static final String RPI_URL = "http://192.168.1.100:5000/notify"; 
    
    private static final OkHttpClient client = new OkHttpClient();
    public static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    public static void sendNotification(String title, String content) {
        String json = "{\"title\": \"" + escape(title) + "\", \"content\": \"" + escape(content) + "\"}";

        RequestBody body = RequestBody.create(json, JSON);
        Request request = new Request.Builder()
                .url(RPI_URL)
                .post(body)
                .build();

        Log.d(TAG, "Sending notification to RPi: " + json);

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                Log.e(TAG, "Failed to send notification", e);
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) {
                    Log.e(TAG, "Unexpected code " + response);
                } else {
                    Log.d(TAG, "Notification sent successfully: " + response.body().string());
                }
                response.close();
            }
        });
    }

    private static String escape(String s) {
        if (s == null) return "";
        return s.replace("\"", "\\\"");
    }
}
