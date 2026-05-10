SELECT date,
       original_content AS content
FROM public.fireant_posts
WHERE date >= %s 
-- AND date < CURRENT_DATE

UNION ALL

SELECT to_timestamp(timestamp) AS date,
       content
FROM public.fb_post
WHERE to_timestamp(timestamp) >= %s 
-- AND to_timestamp(timestamp) < CURRENT_DATE

UNION ALL

SELECT to_timestamp(po.timestamp) AS date,
       rp.rely_content AS content
FROM public.fb_reply AS rp
INNER JOIN public.fb_post AS po ON po.post_id = rp.post_id
WHERE to_timestamp(po.timestamp) >= %s 
-- AND to_timestamp(po.timestamp) < CURRENT_DATE

UNION ALL

SELECT to_timestamp(date) AS date,
       content
FROM public.zalo_chat
WHERE to_timestamp(date) >= %s 
-- AND to_timestamp(date) < CURRENT_DATE
  AND content IS NOT NULL
  AND content <> 'NA'

UNION ALL
  SELECT post_at as date, post_content as content
  FROM yt_post
  WHERE post_at >= %s 
  -- AND post_at < CURRENT_DATE
  and post_content <> ''