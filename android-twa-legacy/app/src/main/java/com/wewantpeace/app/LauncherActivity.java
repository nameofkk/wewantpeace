/*
 * Copyright 2020 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.wewantpeace.app;

import android.app.ActivityManager;
import android.content.pm.ActivityInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;



public class LauncherActivity
        extends com.google.androidbrowserhelper.trusted.LauncherActivity {

    private final Handler mHandler = new Handler(Looper.getMainLooper());

    private void applyTaskDescription() {
        try {
            int primaryColor = Color.parseColor("#0F1729");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                setTaskDescription(new ActivityManager.TaskDescription(
                        "WeWantPeace", R.mipmap.ic_launcher, primaryColor));
            } else {
                Bitmap icon = BitmapFactory.decodeResource(getResources(), R.mipmap.ic_launcher);
                setTaskDescription(new ActivityManager.TaskDescription(
                        "WeWantPeace", icon, primaryColor));
            }
        } catch (Exception ignored) {
            // Activity may be destroyed
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // Set task description BEFORE super.onCreate() which may call finish()
        // in the restored case (savedInstanceState has BROWSER_WAS_LAUNCHED_KEY)
        applyTaskDescription();

        super.onCreate(savedInstanceState);

        if (Build.VERSION.SDK_INT > Build.VERSION_CODES.O) {
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_USER_PORTRAIT);
        } else {
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
        }

        // Set again after super.onCreate() in case it was cleared
        applyTaskDescription();

        // Re-set after Chrome starts and clears our label with null.
        // Chrome calls setTaskDescription(null, null, color) in performPostInflationStartup()
        // which overwrites our label. These delayed calls re-assert our branding.
        // Use post() to survive even if activity is finishing — setTaskDescription
        // still works on the task as long as the token is valid.
        Runnable branding = this::applyTaskDescription;
        mHandler.postDelayed(branding, 1500);
        mHandler.postDelayed(branding, 3000);
        mHandler.postDelayed(branding, 6000);
    }

    @Override
    protected Uri getLaunchingUrl() {
        // Get the original launch Url.
        Uri uri = super.getLaunchingUrl();



        return uri;
    }
}
